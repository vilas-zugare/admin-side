from app.core.database import SessionLocal
from app.models.user import User
import app.models.data # Force load models
from app.core.security import get_password_hash

def create_superuser():
    db = SessionLocal()
    email = "admin@example.com"
    password = "admin"
    
    user = db.query(User).filter(User.email == email).first()
    if user:
        print(f"User {email} already exists.")
        return

    new_user = User(
        email=email,
        name="Super Admin",
        
        hashed_password=get_password_hash(password),
        is_superuser=True
    )
    db.add(new_user)
    db.commit()
    print(f"Superuser created: {email} / {password}")

if __name__ == "__main__":
    create_superuser()
