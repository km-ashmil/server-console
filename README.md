# ServerHub - Server Management Application

A modern web-based server management application built with Django and Python. Manage your servers, connect via SSH terminals, and monitor activity all from a beautiful web interface.

## Features

### 🖥️ Server Management
- Add, edit, and delete servers
- Organize servers into groups
- Tag servers for easy categorization
- Support for password and SSH key authentication
- Real-time server status monitoring

### 🔒 Security
- Encrypted storage of sensitive data (passwords, SSH keys)
- User authentication and authorization
- Secure WebSocket connections for terminal access
- Session management and logging

### 💻 Web Terminal
- Full-featured web-based SSH terminal using xterm.js
- Real-time terminal sessions with WebSocket
- Terminal session management
- Command history and logging
- Quick command shortcuts

### 📊 Dashboard & Monitoring
- Comprehensive dashboard with server statistics
- Activity logs and monitoring
- Connection tracking
- Visual charts and analytics

### 🎨 Modern UI/UX
- Responsive Bootstrap 5 design
- Dark terminal theme
- Intuitive navigation
- Mobile-friendly interface

### ⚡ Performance Optimizations
- Smart database query caching
- Optimized database indexes
- View-level caching for dashboard pages
- Template fragment caching
- User-specific cache management
- Automatic session cleanup
- Cache management commands

## Technology Stack

- **Backend**: Django 4.2, Python 3.8+
- **Frontend**: Bootstrap 5, JavaScript, xterm.js
- **Database**: SQLite (development), PostgreSQL (production)
- **Caching**: Redis (production)
- **WebSockets**: Django Channels
- **SSH**: Paramiko
- **Security**: Cryptography (Fernet encryption)
- **Performance**: Optimized database queries, caching middleware, template fragment caching

## Quick Start

### Prerequisites

- Python 3.8 or higher
- pip (Python package manager)
- Git

### Installation

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd Mahna
   ```

2. **Create a virtual environment**
   ```bash
   python -m venv venv
   
   # On Windows
   venv\Scripts\activate
   
   # On macOS/Linux
   source venv/bin/activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Environment configuration**
   ```bash
   # Copy the example environment file
   cp .env.example .env
   
   # Edit .env file with your settings
   # At minimum, set a secure SECRET_KEY
   ```

5. **Database setup**
   ```bash
   # Run migrations
   python manage.py makemigrations
   python manage.py migrate
   
   # Create a superuser
   python manage.py createsuperuser
   ```

6. **Run the development server**
   ```bash
   python manage.py runserver
   ```

7. **Access the application**
   - Open your browser and go to `http://localhost:8000`
   - Log in with your superuser credentials
   - Start adding servers!

## Configuration

### Environment Variables

Key environment variables in `.env`:

```env
# Required
SECRET_KEY=your-very-secure-secret-key
DEBUG=True

# Database (SQLite for development)
DATABASE_URL=sqlite:///db.sqlite3

# For production with PostgreSQL
# DATABASE_URL=postgresql://user:password@localhost:5432/servermanager

# Redis for production
# REDIS_URL=redis://localhost:6379/0

# Security (for production)
ALLOWED_HOSTS=localhost,127.0.0.1,yourdomain.com
```

### Production Deployment

For production deployment:

1. **Set production environment variables**
   ```env
   DEBUG=False
   SECRET_KEY=your-production-secret-key
   DATABASE_URL=postgresql://user:password@localhost:5432/servermanager
   REDIS_URL=redis://localhost:6379/0
   ALLOWED_HOSTS=yourdomain.com
   SECURE_SSL_REDIRECT=True
   SESSION_COOKIE_SECURE=True
   CSRF_COOKIE_SECURE=True
   ```

2. **Install production dependencies**
   ```bash
   pip install gunicorn daphne
   ```

3. **Collect static files**
   ```bash
   python manage.py collectstatic
   ```

4. **Run with production servers**
   ```bash
   # For HTTP
   gunicorn server_manager.wsgi:application
   
   # For WebSockets (run separately)
   daphne server_manager.asgi:application
   ```

## Usage Guide

### Management Commands

```bash
# Clean up expired server sessions
python manage.py cleanup_sessions --days=1

# Clear expired cache entries
python manage.py clear_expired_cache

# Force clear all cache entries
python manage.py clear_expired_cache --force
```

### Adding Your First Server

1. **Navigate to Servers**
   - Click "Servers" in the sidebar
   - Click "Add Server" button

2. **Fill in server details**
   - **Name**: A friendly name for your server
   - **Host**: IP address or hostname
   - **Port**: SSH port (usually 22)
   - **Username**: SSH username
   - **Authentication**: Choose password or SSH key
   - **Group**: Optional server grouping
   - **Tags**: Optional tags for organization

3. **Test connection**
   - Use the "Test Connection" feature to verify settings
   - Fix any connection issues before saving

### Using the Web Terminal

1. **Connect to a server**
   - Go to server list or server details
   - Click the terminal icon or "Connect" button

2. **Terminal features**
   - Full SSH terminal functionality
   - Copy/paste support
   - Resizable terminal window
   - Quick command buttons
   - Session management

3. **Terminal shortcuts**
   - Use quick command buttons for common tasks
   - Download terminal logs
   - Reconnect if connection drops

### Server Organization

1. **Groups**
   - Create server groups (e.g., "Production", "Development")
   - Assign servers to groups for better organization

2. **Tags**
   - Add tags to servers (e.g., "web", "database", "monitoring")
   - Filter servers by tags

3. **Search and filtering**
   - Use the search bar to find servers quickly
   - Filter by group, status, or tags

## Security Considerations

### Data Encryption
- All sensitive data (passwords, SSH keys) is encrypted using Fernet encryption
- Encryption keys are derived from Django's SECRET_KEY
- Never store plain text credentials

### SSH Security
- Use SSH key authentication when possible
- Regularly rotate SSH keys and passwords
- Monitor connection logs for suspicious activity

### Application Security
- Keep Django and dependencies updated
- Use HTTPS in production
- Set secure cookie flags in production
- Regularly review user access and permissions

## Development

### Project Structure

```
Mahna/
├── authentication/          # User authentication app
├── dashboard/              # Dashboard and analytics
├── servers/               # Server management
├── terminal/              # Web terminal functionality
├── templates/             # HTML templates
├── server_manager/        # Django project settings
├── requirements.txt       # Python dependencies
├── manage.py             # Django management script
└── README.md             # This file
```

### Running Tests

```bash
# Run all tests
python manage.py test

# Run specific app tests
python manage.py test servers
python manage.py test terminal
```

### Code Style

- Follow PEP 8 for Python code
- Use meaningful variable and function names
- Add docstrings to functions and classes
- Keep functions small and focused

## Troubleshooting

### Common Issues

1. **Connection timeouts**
   - Check server firewall settings
   - Verify SSH service is running
   - Increase connection timeout in server settings

2. **Authentication failures**
   - Verify username and credentials
   - Check SSH key format and permissions
   - Review server SSH configuration

3. **WebSocket connection issues**
   - Ensure WebSocket support in your web server
   - Check for proxy/firewall blocking WebSocket connections
   - Verify ASGI configuration

4. **Database issues**
   - Run migrations: `python manage.py migrate`
   - Check database permissions
   - Verify database URL in environment variables

### Logs and Debugging

- Check Django logs for application errors
- Review server connection logs in the admin panel
- Use browser developer tools for frontend issues
- Enable Django debug mode for development

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests for new functionality
5. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Support

For support and questions:
- Check the troubleshooting section
- Review the documentation
- Open an issue on GitHub

---

**ServerHub** - Making server management simple and secure! 🚀