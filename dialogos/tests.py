from django.template import Template, Context

from django.core.urlresolvers import reverse

from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType

from django.test import TestCase

from dialogos.forms import CommentForm
from dialogos.models import Comment
from dialogos.models import deleted_message
from dialogos import views

from contextlib import contextmanager

from xml.etree.ElementTree import XML

def generate_comments(obj, comments, parent=None):
    '''build a tree of comments on the specified object using the provided
    comment specification list/dict data structure'''
    add_spec = dict(
        content_type_id=ContentType.objects.get_for_model(obj).pk,
        object_id=obj.pk,
    )
    for spec in comments:
        children = spec.get('children',None)
        # don't mess with the original spec
        spec_copy = dict(spec)
        spec_copy.update(add_spec)
        if children: del spec_copy['children']
        comment = Comment(**spec_copy)
        comment.insert_at(parent,'last-child',save=True)
        if children:
            generate_comments(obj, children, comment)
            
            
def enable_anonymous_comments(enable):
    if enable:
        views.can_post = lambda u,o: True
    else:
        views.can_post = views.load_can_post()
        

class CommentTests(TestCase):
    
    def setUp(self):
        self.user = User.objects.create_user("gimli", "myaxe@dwarf.org", "gloin")
        self.user2 = User.objects.create_user("aragorn", "theking@gondor.gov", "strider")
        
    def assert_renders(self, tmpl, context, value):
        tmpl = Template(tmpl)
        self.assertEqual(tmpl.render(context), value)
        
    @contextmanager
    def login(self, user, passwd):
        self.assertTrue(self.client.login(username=user, password=passwd))
        yield
        self.client.logout()
        
    @contextmanager
    def enable_anonymous(self):
        enable_anonymous_comments(True)
        yield
        enable_anonymous_comments(False)
    
    def post_comment(self, obj, data, parent=None, verify=False):
        kwargs = dict(
            content_type_id=ContentType.objects.get_for_model(obj).pk,
            object_id=obj.pk,
        )
        path = reverse('post_comment', kwargs=kwargs)
        response = self.client.post(path, data)
        if verify:
            self.assertEqual(response.status_code, 302)
        return response
    
    def post(self, name, **kwargs):
        path = reverse(name, kwargs=kwargs)
        return self.client.post(path)
    
    def test_get_comment_form(self):
        pass
    
    def test_post_comment(self):
        g = User.objects.create(username="Gandalf")

        enable_anonymous_comments(False)
        #verify anonymous comments not allowed
        response = self.post_comment(g, data={
            "name": "Frodo Baggins",
            "comment": "Hello?",
        })
        self.assertEqual(response.status_code, 403)
        # enable them now to avoid many logins
        enable_anonymous_comments(True)
        
        response = self.post_comment(g, data={
            "name": "Frodo Baggins",
            "comment": "Where'd you go?",
        }, verify=True)
        
        self.assertEqual(Comment.objects.count(), 1)
        c = Comment.objects.get()
        self.assertEqual(c.author, None)
        self.assertEqual(c.name, "Frodo Baggins")
        
        response = self.post_comment(g, data={
            "comment": "Where is everyone?"
        })
        self.assertEqual(Comment.objects.count(), 1)
        
        with self.login("gimli", "gloin"):
            response = self.post_comment(g, data={
                "comment": "I thought you were watching the hobbits?"
            }, verify=True)
            self.assertEqual(Comment.objects.count(), 2)
            
            c = Comment.objects.order_by("id")[1]
            self.assertEqual(c.comment, "I thought you were watching the hobbits?")
            self.assertEqual(c.author, self.user)
            
    def test_post_threaded_comment(self):

        def comment(name, comment, parent=None):
            data = {'name' : name, 'comment' : comment}
            if parent: data['parent'] = parent.id
            self.post_comment(self.user, data=data, verify=True)
            return Comment.objects.latest('pk')
        
        with self.enable_anonymous():
            top1 = comment("spammy", "top1")
            top2 = comment("spammy", "top2")
            t1c1 = comment("spammy", "t1c1", top1)
            t1c2 = comment("spammy", "t1c2", top1)
            t2c1 = comment("spammy", "t2c1", top2)
            t2c2 = comment("spammy", "t2c2", top2)

        self.assertTrue([t1c1,t1c2] == list(top1.children.all()))
        self.assertTrue([t2c1,t2c2] == list(top2.children.all()))

    def test_delete_comment(self):
        g = User.objects.create(username="Boromir")
        with self.login("gimli", "gloin"):
            response = self.post_comment(g, data={
                "comment": "Wow, you're a jerk.",
            })
            comment = Comment.objects.get()
        
        response = self.post("delete_comment", comment_id=comment.pk)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Comment.objects.count(), 1)
        
        with self.login("aragorn", "strider"):
            response = self.post("delete_comment", comment_id=comment.pk)
            self.assertEqual(response.status_code, 302)
            self.assertEqual(Comment.objects.count(), 1)
        
        with self.login("gimli", "gloin"):
            response = self.post("delete_comment", comment_id=comment.pk)
            self.assertEqual(response.status_code, 302)
            self.assertEqual(Comment.objects.count(), 0)
            
    def test_delete_threaded_comment(self):
        g = User.objects.create(username="Boromir")
        with self.login("gimli", "gloin"):
            response = self.post_comment(g, data={
                "comment": "Wow, you're a jerk.",
            })
            parent = Comment.objects.get()
            for i in range(5):
                response = self.post_comment(g, data={
                    "comment": "Wow, you're a jerk.",
                    "parent" : parent.id
                })
            self.assertEqual(5, parent.children.count())
            response = self.post("delete_comment", comment_id=parent.pk)
            self.assertEqual(response.status_code, 302)
            parent = Comment.objects.get(pk=parent.pk)
            self.assertEqual(deleted_message, parent.comment)
            
            parent = Comment.objects.get(pk=parent.pk)
            self.assertEqual(5, parent.children.count())
    
    def test_ttag_comment_count(self):
        g = User.objects.create(username="Sauron")
        with self.enable_anonymous():
            self.post_comment(g, data={
                "name": "Gandalf",
                "comment": "You can't win",
            })
            self.post_comment(g, data={
                "name": "Gollum",
                "comment": "We wants our precious",
            })
        
        self.assert_renders(
            "{% load dialogos_tags %}{% comment_count o %}", 
            Context({"o": g}),
            "2"
        )
    
    def test_ttag_comments(self):
        g = User.objects.create(username="Sauron")
        self.post_comment(g, data={
            "name": "Gandalf",
            "comment": "You can't win",
        })
        self.post_comment(g, data={
            "name": "Gollum",
            "comment": "We wants our precious",
        })
        
        c = Context({"o": g})
        self.assert_renders(
            "{% load dialogos_tags %}{% comments o as cs %}",
            c,
            ""
        )
        self.assertEqual(list(c["cs"]), list(Comment.objects.all()))
    
    def test_ttag_comment_form(self):
        g = User.objects.create(username="Sauron")
        c = Context({"o": g})
        self.assert_renders(
            "{% load dialogos_tags %}{% comment_form o as comment_form %}",
            c,
            ""
        )
        self.assertTrue(isinstance(c["comment_form"], CommentForm))
        
        with self.login("gimli", "gloin"):
            c = Context({"o": g, "user": self.user})
            self.assert_renders(
                "{% load dialogos_tags %}{% comment_form o as comment_form %}",
                c,
                ""
            )
            self.assertTrue(isinstance(c["comment_form"], CommentForm))
    
    def test_ttag_comment_target(self):
        g = User.objects.create(username="legolas")
        self.assert_renders(
            "{% load dialogos_tags %}{% comment_target o %}",
            Context({"o": g}),
            "/comment/%d/%d/" % (ContentType.objects.get_for_model(g).pk, g.pk)
        )

    def test_ttag_threaded_comments(self):
        g = User.objects.create(username="jane")
        
        comment_spec = [
            {'author' : g, 'comment' : 'hi', 'children': [
                {'name' : 'joey', 'comment' : 'ho'},
                {'name' : 'joey', 'comment' : 'ha'},
                {'name' : 'joey', 'comment' : 'he'}
            ]},
            {'author' : g, 'comment' : 'hey', 'children': [
                {'name' : 'jimmy', 'comment' : 'heo'},
                {'name' : 'jimmy', 'comment' : 'hea'},
                {'name' : 'jimmy', 'comment' : 'hee'}
            ]}
        ]
        generate_comments(g, comment_spec)
        xmltext = Template(
                    "{% load dialogos_tags %}{% threaded_comments o %}"
                  ).render(Context({"o": g, 'user' : g}))
        dom = XML(xmltext)
            
        nodes = dom.findall('ul/li')
        # top two nodes will be jane
        jane_url = g.get_absolute_url()
        self.assertEqual(2, len(nodes))
        for n in nodes:
            link = n.find('.//a')
            self.assertEqual(jane_url, link.get('href'))
            
        # verify ordering of comments
        for i,n in enumerate(nodes):
            cnodes = n.findall('.//li/p')
            children = comment_spec[i]['children']
            self.assertEqual(len(children), len(cnodes))
            for n,c in zip(cnodes,children):
                self.assertEqual(n.text, c['comment'])
                