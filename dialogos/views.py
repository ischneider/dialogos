import json

from django.conf import settings
from django.http import HttpResponse

from django.views.decorators.http import require_POST
from django.shortcuts import get_object_or_404, redirect
from django.shortcuts import render_to_response
from django.template import RequestContext

from django.contrib.auth.decorators import login_required
from django.contrib.contenttypes.models import ContentType

from dialogos.authorization import load_can_delete
from dialogos.authorization import load_can_edit
from dialogos.authorization import load_can_post
from dialogos.forms import CommentForm
from dialogos.models import Comment
from dialogos.models import deleted_message
from dialogos.signals import commented, comment_updated


can_delete = load_can_delete()
can_edit = load_can_edit()
can_post = load_can_post()


def dehydrate_comment(comment):
    return {
        "pk": comment.pk,
        "comment": comment.comment,
        "author": comment.author.username,
        "name": comment.name,
        "email": comment.email,
        "website": comment.website,
        "submit_date": str(comment.submit_date)
    }


def post_comment(request, content_type_id, object_id, parent_id, 
                 form_class=CommentForm):
    content_type = get_object_or_404(ContentType, pk=content_type_id)
    obj = get_object_or_404(content_type.model_class(), pk=object_id)
    can_post(request.user, obj)
    
    form_args = dict(request=request, obj=obj, user=request.user,
                     parent=parent_id)
                     
    if request.method == 'GET':
        form = form_class(**form_args)
        ctx = RequestContext(request, {'form' : form})
        return render_to_response('dialogos/post_comment.html', ctx)
    else:
        form = form_class(request.POST, **form_args)
    if form.is_valid():
        comment = form.save()
        commented.send(sender=post_comment, comment=comment, request=request)
        if request.is_ajax():
            return HttpResponse(json.dumps({
                "status": "OK",
                "comment": dehydrate_comment(comment)
            }), mimetype="application/json")
    else:
        if request.is_ajax():
            return HttpResponse(json.dumps({
                "status": "ERROR",
                "errors": form.errors
            }), mimetype="application/json")
        else:
            return HttpResponse('invalid POST : %s' % form.errors, status=400)
    redirect_to = request.POST.get("next")
    # light security check -- make sure redirect_to isn't garbage.
    if not redirect_to or " " in redirect_to or redirect_to.startswith("http"):
        redirect_to = obj
    return redirect(redirect_to)


@login_required
@require_POST
def edit_comment(request, comment_id, form_class=CommentForm):
    comment = get_object_or_404(Comment, pk=comment_id)
    form = form_class(request.POST, instance=comment, request=request, 
                      obj=comment.content_object, user=request.user)
    if form.is_valid():
        comment = form.save()
        comment_updated.send(sender=edit_comment, comment=comment, request=request)
        if request.is_ajax():
            return HttpResponse(json.dumps({
                "status": "OK",
                "comment": dehydrate_comment(comment)
            }), mimetype="application/json")
    else:
        if request.is_ajax():
            return HttpResponse(json.dumps({
                "status": "ERROR",
                "errors": form.errors
            }), mimetype="application/json")
    redirect_to = request.POST.get("next")
    # light security check -- make sure redirect_to isn't garbage.
    if not redirect_to or " " in redirect_to or redirect_to.startswith("http"):
        redirect_to = comment.content_object
    return redirect(redirect_to)


@login_required
@require_POST
def delete_comment(request, comment_id):
    comment = get_object_or_404(Comment, pk=comment_id)
    obj = comment.content_object
    if can_delete(request.user, comment):
        if comment.children.count():
            comment.comment = deleted_message
            comment.save()
        else:
            comment.delete()
        if request.is_ajax():
            return HttpResponse(json.dumps({"status": "OK"}))
    else:
        if request.is_ajax():
            return HttpResponse(json.dumps({
                "status": "ERROR", 
                "errors": "You do not have permission to delete this comment."}
            ))
    return redirect(obj)
