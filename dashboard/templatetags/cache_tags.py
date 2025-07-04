from django import template
from django.core.cache import cache
from django.utils.safestring import mark_safe
import hashlib

register = template.Library()

@register.tag('user_cache')
def do_user_cache(parser, token):
    """
    Template tag that caches content for each user separately.
    
    Usage:
    {% user_cache [timeout_in_seconds] [fragment_name] %}
        .. some expensive processing ..
    {% end_user_cache %}
    """
    nodelist = parser.parse(('end_user_cache',))
    parser.delete_first_token()
    
    tokens = token.split_contents()
    if len(tokens) < 3:
        raise template.TemplateSyntaxError(
            "%r tag requires at least 2 arguments." % tokens[0]
        )
        
    timeout = tokens[1]
    try:
        timeout = int(timeout)
    except ValueError:
        timeout = template.Variable(timeout)
        
    fragment_name = tokens[2]
    if not (fragment_name[0] == fragment_name[-1] and fragment_name[0] in ('"', "'")):
        fragment_name = template.Variable(fragment_name)
    else:
        fragment_name = fragment_name[1:-1]
        
    vary_on = []
    if len(tokens) > 3:
        vary_on = tokens[3:]
        
    return UserCacheNode(nodelist, timeout, fragment_name, vary_on)

class UserCacheNode(template.Node):
    def __init__(self, nodelist, timeout, fragment_name, vary_on):
        self.nodelist = nodelist
        self.timeout = timeout
        self.fragment_name = fragment_name
        self.vary_on = vary_on
        
    def render(self, context):
        # Get timeout
        if isinstance(self.timeout, template.Variable):
            try:
                timeout = self.timeout.resolve(context)
            except template.VariableDoesNotExist:
                timeout = 300
        else:
            timeout = self.timeout
            
        # Get fragment name
        if isinstance(self.fragment_name, template.Variable):
            try:
                fragment_name = self.fragment_name.resolve(context)
            except template.VariableDoesNotExist:
                fragment_name = self.fragment_name
        else:
            fragment_name = self.fragment_name
            
        # Get user ID
        user_id = 'anonymous'
        if 'user' in context and hasattr(context['user'], 'id'):
            user_id = context['user'].id
            
        # Build vary_on values
        vary_values = []
        for var in self.vary_on:
            if var[0] == var[-1] and var[0] in ('"', "'"):
                vary_values.append(var[1:-1])
            else:
                try:
                    vary_values.append(template.Variable(var).resolve(context))
                except template.VariableDoesNotExist:
                    vary_values.append(None)
                    
        # Create cache key
        cache_key = 'template_fragment_{}_{}'.format(
            fragment_name,
            hashlib.md5(f'{user_id}_{"_".join(str(v) for v in vary_values)}'.encode()).hexdigest()
        )
        
        # Try to get from cache
        content = cache.get(cache_key)
        if content is None:
            content = self.nodelist.render(context)
            cache.set(cache_key, content, timeout)
            
        return mark_safe(content)

@register.simple_tag(takes_context=True)
def cache_key(context, name):
    """
    Generate a cache key based on the user and a name.
    
    Usage:
    {% cache_key "dashboard_stats" as stats_key %}
    """
    user_id = 'anonymous'
    if 'user' in context and hasattr(context['user'], 'id'):
        user_id = context['user'].id
        
    return f'template_fragment_{name}_{user_id}'