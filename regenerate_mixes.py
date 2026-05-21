from app import create_app, db
from app.services.recommender import generate_daily_mixes_for_all_users

app = create_app()
with app.app_context():
    generate_daily_mixes_for_all_users()
