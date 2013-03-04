# -*- coding: utf-8 -*-
import pytest
import authcode
from flask import Flask, g, session
from orm import SQLAlchemy

from helpers import *


def get_flask_app(**kwargs):
    db = SQLAlchemy()
    auth = authcode.Auth(SECRET_KEY, db=db, **kwargs)

    class User(auth.User):
        pass

    db.create_all()
    user = User(login=u'meh', password='foobar')
    db.add(user)
    db.commit()

    app = Flask('test')
    app.secret_key = os.urandom(32)
    app.testing = True
    authcode.setup_for_flask(auth, app, views=False)

    @app.route('/login')
    def login():
        user = User.by_id(1)
        auth.login(user)
        return 'login'

    @app.route('/logout')
    def logout():
        auth.logout()
        return 'logout'

    return auth, app, user


def test_setup_for_flask():
    auth, app, user = get_flask_app()
    client = app.test_client()

    @app.route('/get')
    def get_user():
        if g.user:
            return g.user.login
        return ''

    resp = client.get('/get')
    assert resp.data == ''
    
    client.get('/login')
    resp = client.get('/get')
    assert resp.data == u'meh'

    client.get('/logout')
    resp = client.get('/get')
    assert resp.data == ''


def test_protected():
    auth, app, user = get_flask_app()
    client = app.test_client()

    @app.route('/admin')
    @auth.protected()
    def admin():
        return ''

    resp = client.get('/admin')
    assert resp.status == '303 SEE OTHER'

    client.get('/login')
    resp = client.get('/admin')
    print resp.data
    assert resp.status == '200 OK'


def test_signin_url():
    auth, app, user = get_flask_app()
    auth.url_sign_in = '/sign-in/'
    client = app.test_client()

    @app.route('/admin1')
    @auth.protected()
    def admin1():
        return ''

    @app.route('/admin2')
    @auth.protected(url_sign_in='/users/sign-in/')
    def admin2():
        return ''

    resp = client.get('/admin1')
    assert resp.headers.get('location') == 'http://localhost/sign-in/'

    resp = client.get('/admin2')
    assert resp.headers.get('location') == 'http://localhost/users/sign-in/'

    auth.url_sign_in = lambda request: '/login'
    resp = client.get('/admin1')
    assert resp.headers.get('location') == 'http://localhost/login'    


def test_protected_role():
    auth, app, user = get_flask_app(roles=True)
    client = app.test_client()

    @app.route('/admin1')
    @auth.protected(role='admin')
    def admin1():
        return 'admin1'

    @app.route('/admin2')
    @auth.protected(roles=['editor', 'admin'])
    def admin2():
        return 'admin2'

    client.get('/login')

    resp = client.get('/admin1')
    assert resp.status == '303 SEE OTHER'
    resp = client.get('/admin2')
    assert resp.status == '303 SEE OTHER'

    user.add_role('admin')
    auth.db.commit()
    
    resp = client.get('/admin1?r=123')
    assert resp.status == '200 OK'
    assert resp.data == 'admin1'

    resp = client.get('/admin2?r=123')
    assert resp.status == '200 OK'
    assert resp.data == 'admin2'


def test_protected_tests():
    auth, app, user = get_flask_app(roles=True)
    client = app.test_client()

    log = []

    def test1(*args, **kwargs):
        log.append('test1')
        return True

    def test2(*args, **kwargs):
        log.append('test2')
        return True

    def fail(*args, **kwargs):
        log.append('fail')
        return False

    @app.route('/admin1')
    @auth.protected(test1, test2)
    def admin1():
        return ''

    @app.route('/admin2')
    @auth.protected(test1, fail, test2)
    def admin2():
        return ''

    client.get('/login')
    resp = client.get('/admin1')
    assert log == ['test1', 'test2']
    assert resp.status == '200 OK'

    resp = client.get('/admin2')
    assert log == ['test1', 'test2', 'test1', 'fail']
    assert resp.status == '303 SEE OTHER'


def test_protected_csrf():
    auth, app, user = get_flask_app(roles=True)
    client = app.test_client()

    @app.route('/gettoken')
    @auth.protected()
    def gettoken():
        return auth.get_csfr_token()

    @app.route('/delete', methods=['GET', 'POST'])
    @auth.protected(force_csrf=True)
    def delete():
        return ''

    @app.route('/update', methods=['GET', 'POST'])
    @auth.protected()
    def update():
        return ''

    @app.route('/whatever', methods=['GET', 'POST'])
    @auth.protected(csrf=False)
    def whatever():
        return ''

    client.get('/login')

    resp = client.get('/delete')
    assert resp.status == '403 FORBIDDEN'

    resp = client.post('/update')
    assert resp.status == '403 FORBIDDEN'

    resp = client.post('/whatever')
    assert resp.status == '200 OK'

    resp = client.get('/gettoken')
    token = resp.data

    resp = client.get('/delete?' + auth.csrf_key + '=' + token)
    assert resp.status == '200 OK'

    resp = client.post('/update', data={auth.csrf_key: token})
    assert resp.status == '200 OK'

    resp = client.post('/update', headers={'X-CSRFToken': token})
    assert resp.status == '200 OK'


