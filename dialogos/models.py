from datetime import datetime

from django.db import models

from django.contrib.auth.models import User
from django.contrib.contenttypes.generic import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.core.urlresolvers import reverse

from mptt.models import MPTTModel
from mptt.models import TreeForeignKey


deleted_message = "- This comment has been deleted -"

class Comment(MPTTModel):
    
    author = models.ForeignKey(User, null=True, related_name="comments")
    
    name = models.CharField(max_length=100)
    email = models.CharField(max_length=255, blank=True)
    website = models.CharField(max_length=255, blank=True)
    
    content_type = models.ForeignKey(ContentType)
    object_id = models.IntegerField()
    content_object = GenericForeignKey()
    
    comment = models.TextField()
    
    submit_date = models.DateTimeField(default=datetime.now)
    ip_address = models.IPAddressField(null=True)
    public = models.BooleanField(default=True)
    
    parent = TreeForeignKey('self', null=True, blank=True, related_name='children')
    
    def __unicode__(self):
        return "pk=%d" % self.pk
    
    def reply_url(self):
        return reverse('post_comment', args=[
            self.content_type.id,
            self.object_id,
            self.id
        ])
        
    def comment_url(self):
        return reverse('post_comment', args=[
            self.content_type.id,
            self.object_id
        ])