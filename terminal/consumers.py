import json
import asyncio
import paramiko
import threading
import uuid
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth.models import User
from servers.models import Server, ServerConnection, ServerLog
from io import StringIO
import socket
import time

class TerminalConsumer(AsyncWebsocketConsumer):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.server_id = None
        self.server = None
        self.ssh_client = None
        self.ssh_channel = None
        self.session_id = None
        self.connection_obj = None
        self.read_thread = None
        self.connected = False
        self.loop = None

    async def connect(self):
        self.server_id = self.scope['url_route']['kwargs']['server_id']
        self.user = self.scope['user']
        
        if not self.user.is_authenticated:
            await self.close()
            return
        
        # Get server and check permissions
        self.server = await self.get_server()
        if not self.server:
            await self.close()
            return
        
        # Generate session ID
        self.session_id = str(uuid.uuid4())
        
        # Join room group
        self.room_group_name = f'terminal_{self.server_id}_{self.session_id}'
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        
        await self.accept()
        
        # Create connection record
        await self.create_connection_record()
        
        # Send initial message
        await self.send(text_data=json.dumps({
            'type': 'status',
            'message': f'Connecting to {self.server.name}...'
        }))
        
        # Start SSH connection in background
        asyncio.create_task(self.connect_ssh())

    async def disconnect(self, close_code):
        # Clean up SSH connection
        if self.ssh_channel:
            try:
                self.ssh_channel.close()
            except:
                pass
        
        if self.ssh_client:
            try:
                self.ssh_client.close()
            except:
                pass
        
        # Update connection record
        if self.connection_obj:
            await self.update_connection_record(False)
        
        # Leave room group
        if hasattr(self, 'room_group_name'):
            await self.channel_layer.group_discard(
                self.room_group_name,
                self.channel_name
            )
        
        # Log disconnection
        if self.server:
            await self.log_activity('connection', 'Disconnected from terminal')

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
            message_type = data.get('type')
            
            if message_type == 'command':
                command = data.get('data', '')
                await self.send_command(command)
            elif message_type == 'resize':
                cols = data.get('cols', 80)
                rows = data.get('rows', 24)
                await self.resize_terminal(cols, rows)
        except json.JSONDecodeError:
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': 'Invalid JSON data'
            }))

    async def connect_ssh(self):
        """Establish SSH connection"""
        try:
            # Create SSH client
            self.ssh_client = paramiko.SSHClient()
            self.ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            
            # Prepare connection parameters
            connect_params = {
                'hostname': self.server.hostname,
                'port': self.server.port,
                'username': self.server.username,
                'timeout': self.server.timeout,
            }
            
            # Add authentication
            if self.server.auth_method == 'password':
                connect_params['password'] = self.server.get_password()
            elif self.server.auth_method in ['key', 'key_password']:
                private_key_str = self.server.get_private_key()
                private_key_file = StringIO(private_key_str)
                
                try:
                    if self.server.auth_method == 'key_password':
                        key_password = self.server.get_key_password()
                        private_key = paramiko.RSAKey.from_private_key(private_key_file, password=key_password)
                    else:
                        private_key = paramiko.RSAKey.from_private_key(private_key_file)
                    connect_params['pkey'] = private_key
                except Exception:
                    try:
                        private_key_file.seek(0)
                        if self.server.auth_method == 'key_password':
                            key_password = self.server.get_key_password()
                            private_key = paramiko.Ed25519Key.from_private_key(private_key_file, password=key_password)
                        else:
                            private_key = paramiko.Ed25519Key.from_private_key(private_key_file)
                        connect_params['pkey'] = private_key
                    except Exception as e:
                        await self.send(text_data=json.dumps({
                            'type': 'error',
                            'message': f'Invalid private key: {str(e)}'
                        }))
                        return
            
            # Connect
            # Create a wrapper function to handle keyword arguments
            def connect_ssh_with_params():
                return self.ssh_client.connect(**connect_params)
                
            await asyncio.get_event_loop().run_in_executor(
                None, connect_ssh_with_params
            )
            
            # Create interactive shell
            self.ssh_channel = self.ssh_client.invoke_shell(
                term='xterm-256color',
                width=80,
                height=24
            )
            
            self.connected = True
            
            # Send success message
            await self.send(text_data=json.dumps({
                'type': 'status',
                'message': f'Connected to {self.server.name}'
            }))
            
            # Update server status
            await self.update_server_status('online')
            
            # Log connection
            await self.log_activity('connection', 'Connected to terminal')
            
            # Store the current event loop for the background thread
            self.loop = asyncio.get_event_loop()
            
            # Start reading from SSH channel
            self.read_thread = threading.Thread(target=self.read_ssh_output)
            self.read_thread.daemon = True
            self.read_thread.start()
            
        except paramiko.AuthenticationException:
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': 'Authentication failed'
            }))
            await self.update_server_status('error', 'Authentication failed')
            
        except socket.timeout:
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': 'Connection timeout'
            }))
            await self.update_server_status('offline', 'Connection timeout')
            
        except Exception as e:
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': f'Connection failed: {str(e)}'
            }))
            await self.update_server_status('error', str(e))

    def read_ssh_output(self):
        """Read output from SSH channel and send to WebSocket"""
        while self.connected and self.ssh_channel:
            try:
                if self.ssh_channel.recv_ready():
                    data = self.ssh_channel.recv(1024)
                    if data:
                        asyncio.run_coroutine_threadsafe(
                            self.send(text_data=json.dumps({
                                'type': 'output',
                                'data': data.decode('utf-8', errors='ignore')
                            })),
                            self.loop
                        )
                else:
                    time.sleep(0.01)
            except Exception as e:
                asyncio.run_coroutine_threadsafe(
                    self.send(text_data=json.dumps({
                        'type': 'error',
                        'message': f'Read error: {str(e)}'
                    })),
                    self.loop
                )
                break

    async def send_command(self, command):
        """Send command to SSH channel"""
        if self.ssh_channel and self.connected:
            try:
                self.ssh_channel.send(command)
                # Log command if it's not just keystrokes
                if command.strip() and command != '\r' and command != '\n':
                    await self.log_activity('command', f'Executed: {command.strip()}')
            except Exception as e:
                await self.send(text_data=json.dumps({
                    'type': 'error',
                    'message': f'Command send error: {str(e)}'
                }))

    async def resize_terminal(self, cols, rows):
        """Resize terminal"""
        if self.ssh_channel and self.connected:
            try:
                self.ssh_channel.resize_pty(width=cols, height=rows)
            except Exception as e:
                await self.send(text_data=json.dumps({
                    'type': 'error',
                    'message': f'Resize error: {str(e)}'
                }))

    @database_sync_to_async
    def get_server(self):
        """Get server object"""
        try:
            return Server.objects.get(id=self.server_id, created_by=self.user)
        except Server.DoesNotExist:
            return None

    @database_sync_to_async
    def create_connection_record(self):
        """Create connection record"""
        self.connection_obj = ServerConnection.objects.create(
            server=self.server,
            user=self.user,
            session_id=self.session_id
        )

    @database_sync_to_async
    def update_connection_record(self, is_active):
        """Update connection record"""
        if self.connection_obj:
            self.connection_obj.is_active = is_active
            self.connection_obj.save()

    @database_sync_to_async
    def update_server_status(self, status, error_message=''):
        """Update server status"""
        from django.utils import timezone
        self.server.status = status
        self.server.last_checked = timezone.now()
        if error_message:
            self.server.last_error = error_message
        else:
            self.server.last_error = ''
        self.server.save()

    @database_sync_to_async
    def log_activity(self, log_type, message):
        """Log activity"""
        ServerLog.objects.create(
            server=self.server,
            user=self.user,
            log_type=log_type,
            message=message,
            session_id=self.session_id
        )