from django import forms
from django.core.urlresolvers import reverse

from django.contrib.contenttypes.models import ContentType

from dialogos.models import Comment


class CommentForm(forms.ModelForm):
    
    class Meta:
        model = Comment
        fields = [
            "name", "email", "website", "comment", "parent"
        ]
        widgets = {
            "parent" : forms.widgets.HiddenInput
        }
    
    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop("request", None)
        self.obj = kwargs.pop("obj")
        self.user = kwargs.pop("user")
        self.parent = kwargs.pop("parent", None)
        super(CommentForm, self).__init__(*args, **kwargs)
        if self.user and not self.user.is_anonymous():
            del self.fields["name"]
            del self.fields["email"]
            del self.fields["website"]
            
    def action_url(self):
        content_type = ContentType.objects.get_for_model(self.obj)
        return reverse('post_comment', args=[
            content_type.id,
            self.obj.pk,
            self.parent if self.parent else None
        ])
    
    def save(self, commit=True):
        comment = super(CommentForm, self).save(commit=False)
        comment.ip_address = self.request.META.get("REMOTE_ADDR", None)
        comment.content_type = ContentType.objects.get_for_model(self.obj)
        comment.object_id = self.obj.pk
        if self.parent:
            comment.parent = Comment.objects.get(pk=self.parent)
        if not self.user.is_anonymous():
            comment.author = self.user
        if commit:
            comment.save()
        return comment
