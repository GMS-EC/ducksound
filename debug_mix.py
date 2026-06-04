from app import create_app, db
from app.models import DailyMix

app = create_app()
with app.app_context():
    mix = DailyMix.query.first()
    if mix:
        print(f"Mix ID: {mix.id}")
        print(f"Songs: {len(mix.canciones)}")
    else:
        print("No mix found")
