from flask import Flask, render_template, redirect, url_for, flash, abort, session
from flask_bootstrap import Bootstrap
from flask_ckeditor import CKEditor
from werkzeug.security import generate_password_hash, check_password_hash
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import relationship
from flask_login import UserMixin, login_user, LoginManager, login_required, current_user, logout_user
from forms import CreatePostForm, RegisterForm, LoginForm, CommentForm
from datetime import date
from functools import wraps
from hashlib import md5
import os
from flask_session import Session

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get("SECRET_KEY", "nDMRiF6HVdjyOjuPl63bPf")
app.config['SESSION_COOKIE_SECURE'] = True
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['REMEMBER_COOKIE_SECURE'] = True
app.config['SESSION_TYPE'] = 'filesystem'
Session(app)
ckeditor = CKEditor(app)
Bootstrap(app)

##CONNECT TO DB
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get("DATABASE_URL",  "sqlite:///blog.db")
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)
app.app_context().push()

login_manager = LoginManager()
login_manager.init_app(app)

@login_manager.user_loader
def load_user(user_id):
    return db.session.query(User).get(int(user_id))

##CONFIGURE TABLES
class User(UserMixin, db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(250), unique=True, nullable=False)
    password = db.Column(db.String(250), nullable=False)
    name = db.Column(db.String(250), nullable=False)

    #This will act like a List of BlogPost objects attached to each User. 
    #The "author" refers to the author property in the BlogPost class.
    posts = relationship('BlogPost', back_populates="author")

    comments = relationship("Comment", back_populates="comment_author")

class BlogPost(db.Model):
    __tablename__ = "blog_posts"
    id = db.Column(db.Integer, primary_key=True)

    #Create Foreign Key, "users.id" the users refers to the tablename of User.
    author_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    #Create reference to the User object, the "posts" refers to the posts protperty in the User class.
    author = relationship("User", back_populates="posts")

    comments = relationship("Comment", back_populates="parent_post")

    title = db.Column(db.String(250), unique=True, nullable=False)
    subtitle = db.Column(db.String(250), nullable=False)
    date = db.Column(db.String(250), nullable=False)
    body = db.Column(db.Text, nullable=False)
    img_url = db.Column(db.String(250), nullable=False)

class Comment(db.Model):
    __tablename__ = "comments"
    id = db.Column(db.Integer, primary_key=True)

    #Establish a relationship between the User and Comment
    author_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    comment_author = relationship('User', back_populates="comments")
    #Establish a relationship between the BlogPost and Comment
    post_id = db.Column(db.Integer, db.ForeignKey("blog_posts.id"))
    parent_post = relationship("BlogPost", back_populates="comments")

    comment_text = db.Column(db.Text, nullable=False)
    
db.create_all()


def admin_only(f):
    wraps(f)
    def decorated_function(*args, **kwargs):
        if current_user.is_anonymous or current_user.id != 1:
            abort(403)
        return f(*args, **kwargs)
    return decorated_function

def gravatar_url(email, size=100, rating='g', default='retro', force_default=False):
    hash_value = md5(email.lower().encode('utf-8')).hexdigest()
    return f"https://www.gravatar.com/avatar/{hash_value}?s={size}&d={default}&r={rating}&f={force_default}"
app.jinja_env.globals.update(gravatar_url=gravatar_url)


@app.route('/')
def get_all_posts():
    posts = db.session.query(BlogPost).all()
    return render_template("index.html", all_posts=posts)


@app.route('/register', methods=['GET', 'POST'])
def register():
    form = RegisterForm()
    if form.validate_on_submit():
        if db.session.query(User).filter_by(email=form.email.data).first():
            flash("This email is already registered, login instead.")
            return redirect('login') 
        new_user = User(
            email = form.email.data,
            password = generate_password_hash(password=form.password.data, method="pbkdf2:sha256", salt_length=8),
            name = form.name.data
        )
        db.session.add(new_user)
        db.session.commit()
        login_user(new_user)
        return redirect(url_for('get_all_posts'))
    return render_template("register.html", form=form)


@app.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    print(form.validate_on_submit())
    if form.validate_on_submit():
        try:
            user = db.session.query(User).filter_by(email=form.email.data).first()
            print(check_password_hash(user.password, form.password.data))
            if check_password_hash(user.password, form.password.data):
                login_user(user)
                session['user_id'] = user.id
                return redirect(url_for('get_all_posts'))
            else:
                flash("Password is incorrect, please try again.")

        except AttributeError:
            flash("That email is not registered, please try again.")
        
        return redirect(url_for("login"))
    
    return render_template("login.html", form=form)


@app.route('/logout')
@login_required
def logout():
    logout_user()
    session.clear()
    return redirect(url_for('get_all_posts'))


@app.route("/post/<int:post_id>", methods=['GET', 'POST'])
def show_post(post_id):
    requested_post = db.session.query(BlogPost).get(post_id)

    form = CommentForm()
    if form.validate_on_submit():
        if current_user.is_authenticated:
            comment = Comment(
                comment_text = form.comment.data,
                comment_author = current_user,
                parent_post = requested_post
            )
            db.session.add(comment)
            db.session.commit()
            return redirect(url_for('show_post', post_id=post_id))
        else:
            flash("You need to login or register to comment.")
            return redirect(url_for('login'))

    return render_template("post.html", post=requested_post, form=form)


@app.route("/about")
def about():
    return render_template("about.html")


@app.route("/contact")
def contact():
    return render_template("contact.html")


@app.route("/new-post", methods=['GET', 'POST'], endpoint='add_new_post')
@admin_only
def add_new_post():
    form = CreatePostForm()
    if form.validate_on_submit():
        new_post = BlogPost(
            title=form.title.data,
            subtitle=form.subtitle.data,
            body=form.body.data,
            img_url=form.img_url.data,
            author=current_user,
            date=date.today().strftime("%B %d, %Y")
        )
        db.session.add(new_post)
        db.session.commit()
        return redirect(url_for("get_all_posts"))
    return render_template("make-post.html", form=form)


@app.route("/edit-post/<int:post_id>", methods=['GET', 'POST'], endpoint='edit_post')
@admin_only
def edit_post(post_id):
    post = db.session.query(BlogPost).get(post_id)
    edit_form = CreatePostForm(
        title=post.title,
        subtitle=post.subtitle,
        img_url=post.img_url,
        body=post.body
    )
    if edit_form.validate_on_submit():
        post.title = edit_form.title.data
        post.subtitle = edit_form.subtitle.data
        post.img_url = edit_form.img_url.data
        post.body = edit_form.body.data
        db.session.commit()
        return redirect(url_for("show_post", post_id=post.id))

    return render_template("make-post.html", form=edit_form)


@app.route("/delete/<int:post_id>", endpoint='delete_post')
@admin_only
def delete_post(post_id):
    post_to_delete = db.session.query(BlogPost).get(post_id)
    db.session.delete(post_to_delete)
    db.session.commit()
    return redirect(url_for('get_all_posts'))
