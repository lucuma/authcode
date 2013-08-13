# -*- coding: utf-8 -*-
from flask import url_for
from authcode import Auth, setup_for_flask

import settings
from app import app, db, mailer


class UserMixin(object):
    email = db.Column(db.Unicode)

auth = Auth(settings.SECRET_KEY, db=db, UserMixin=UserMixin, roles=True,
    **settings.AUTH_SETTINGS)

User = auth.User


def send_email(user, subject, msg):
    if not user.email:
        return
    try:
        mailer.send(subject, html_content=msg,
            from_email=settings.MAILER_SENDER, to=user.email)
    except:
        pass


setup_for_flask(auth, app, views=True, send_email=send_email)
