import os
from flask import Flask, render_template, request, jsonify, url_for, redirect, session
from flask.ext.sqlalchemy import SQLAlchemy
from flaskext.bcrypt import Bcrypt

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ['DATABASE_URL']
app.secret_key = '\xe3\xef\xcaD\xf3q\xfel\xd9+3$\xb5\x13\x83L\x8d\xe49\xca\xa4]\x9f\x10'
app.debug = True

db = SQLAlchemy(app)
bcrypt = Bcrypt(app)

class User(db.Model):
    name = db.Column(db.String(80), primary_key=True)
    password = db.Column(db.String(80))

    def __init__(self, name, password):
        self.name = name
        self.password = bcrypt.generate_password_hash(password)

class Lifter(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80))
    weight = db.Column(db.Numeric(precision=5, scale=1))
    division_id = db.Column(db.Integer, db.ForeignKey('division.id'))

    def __init__(self, name, weight, division):
        self.name = name
        self.weight = weight
        self.division = division

    def __repr__(self):
        return '<Name %r>' % self.name

    def calc_total(self):
        return (max([attempt.weight for attempt in self.attempts
        if attempt.lift.name == "Bench Press" and not attempt.miss] + [0]) +
            max([attempt.weight for attempt in self.attempts
                if attempt.lift.name == "Deadlift" and not attempt.miss] + [0]))

    total = property(calc_total)

    def calc_wilks(self):
        lbs_to_kg = 0.45359237
        x = lbs_to_kg * float(self.weight)
        if 'Female' in self.division.name:
            a=594.31747775582
            b=-27.23842536447
            c=0.82112226871
            d=-0.00930733913
            e=0.00004731582
            f=-0.00000009054
        else:
            a=-216.0475144
            b=16.2606339
            c=-0.002388645
            d=-0.00113732
            e=7.01863e-06
            f=-1.291e-08

        return lbs_to_kg * float(self.total) * 500 / (a + b*x + c*x**2 + d*x**3 +
                e*x**4 + f*x**5)

    wilks = property(calc_wilks)

    def attempt(self, lift_name, n):
        return next(iter([attempt for attempt in self.attempts if attempt.lift.name == lift_name and attempt.number == n]), None)


class Division(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80))
    lifters = db.relation(Lifter, primaryjoin=(id == Lifter.division_id),
                         backref=db.backref('division'))

    def __init__(self, name):
        self.name = name

    def __repr__(self):
        return "<Division %s>" % self.name

    def calc_leader(self):
        return  max(self.lifters, key=lambda l: l.wilks)

    leader = property(calc_leader)

class Lift(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80))

    def __init__(self, name):
        self.name = name

    def __repr__(self):
        return "<Lift %s>" % self.name

class Attempt(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    number = db.Column(db.Integer)
    miss = db.Column(db.Boolean)
    weight = db.Column(db.Numeric(precision=5, scale=1))
    lifter_id = db.Column(db.Integer, db.ForeignKey('lifter.id'))
    lift_id = db.Column(db.Integer, db.ForeignKey('lift.id'))
    lifter = db.relation(Lifter, primaryjoin=(lifter_id == Lifter.id),
                         backref=db.backref('attempts'))
    lift = db.relation(Lift, primaryjoin=(Lift.id == lift_id),
                         backref=db.backref('attempts'))

    def __init__(self, number, lift, weight, miss=None):
        self.lift = lift
        self.number = number
        self.weight = weight
        if miss:
            self.miss = True
        else:
            self.miss = False

    def __repr__(self):
        miss = ''
        if self.miss:
            miss = 'MISSED '

        return "<Attempt %d: %s, %s>" % (self.number, self.lift.name, str(self.weight))

@app.route('/')
def index():
    return render_template('index.html',
            lifters=sorted(sorted(Lifter.query.all(),
                key=lambda l:l.wilks, reverse=True),
                key=lambda l:l.division.name), logged_in=session.get('logged_in', False))

@app.route('/login/', methods = ['POST'])
def login():
    name = request.form['name']
    password = request.form['password']
    u = User.query.filter_by(name = name).first_or_404()
    if (bcrypt.check_password_hash(u.password, password)):
            session['logged_in'] = True
    return redirect(url_for('index'))

@app.route('/add_lifter/', methods=['POST'])
def add_lifter():
    name = request.form['name']
    weight = float(request.form['weight'])
    division = Division.query.filter_by(name=request.form['division']).first()

    new = Lifter(name, weight, division)
    db.session.add(new)
    db.session.commit()

    return redirect(url_for('index'))


@app.route('/add_attempt/', methods=['POST'])
def add_attempt():
    lifter = Lifter.query.filter_by(name=request.form['name']).first()
    lift = Lift.query.filter_by(name=request.form['lift']).first()
    weight = float(request.form['weight'])
    number = int(request.form['number'])
    miss = request.form['miss']
    if miss == 'false':
        miss = False
    else:
        miss = True

    attempt = next(iter(a for a in lifter.attempts
                if a.lift == lift and a.number == number), None)

    if attempt:
        attempt.weight = weight
        attempt.miss = miss
    else:
        attempt = Attempt(number,lift, weight, miss)
        lifter.attempts.append(attempt)

    db.session.add(attempt)
    db.session.commit()

    return render_template('index.html',
            lifters=sorted(sorted(Lifter.query.all(),
                key=lambda l:l.wilks, reverse=True),
                key=lambda l:l.division.name), logged_in=session.get('logged_in', False))


if __name__ == "__main__":
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)

