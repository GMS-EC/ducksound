from app import create_app, db
app = create_app()
with app.app_context():
    res = db.session.execute(db.text('SELECT count(*) FROM daily_mix_canciones')).scalar()
    print(f'Total rows in daily_mix_canciones: {res}')
