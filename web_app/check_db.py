from lib.database import get_db
from lib.models.generated_models import Countries, Currencies

def check_db():
    with get_db() as db:
        # Check countries
        countries = db.query(Countries).all()
        print("\nCountries:")
        for c in countries:
            print(f"ID: {c.id}, Name: {c.country_name}, Capital: {c.capital_city}, Currency ID: {c.currency_id}")
        
        # Check currencies
        currencies = db.query(Currencies).all()
        print("\nCurrencies:")
        for c in currencies:
            print(f"ID: {c.id}, Code: {c.currency_code}, Name: {c.currency_name}")

if __name__ == '__main__':
    check_db()
