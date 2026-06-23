from datetime import date

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import EmissionFactor
from app.services.calculation import calculate_kgco2e, get_valid_factor


def test_get_valid_factor_uses_activity_date_not_latest_factor():
    engine = create_engine("sqlite:///:memory:")
    TestingSession = sessionmaker(bind=engine)
    Base.metadata.create_all(engine)

    with TestingSession() as db:
        db.add_all(
            [
                EmissionFactor(
                    scope="Scope 1",
                    source_name="Diesel",
                    activity_category="Stationary Combustion",
                    unit="KL",
                    factor_kgco2e_per_unit=2600,
                    factor_unit="kgCO2e/KL",
                    source="Historical test source",
                    version="2023-expired",
                    valid_from=date(2023, 1, 1),
                    valid_to=date(2023, 12, 31),
                ),
                EmissionFactor(
                    scope="Scope 1",
                    source_name="Diesel",
                    activity_category="Stationary Combustion",
                    unit="KL",
                    factor_kgco2e_per_unit=2800,
                    factor_unit="kgCO2e/KL",
                    source="Current test source",
                    version="2024-active",
                    valid_from=date(2024, 1, 1),
                    valid_to=None,
                ),
            ]
        )
        db.commit()

        historical = get_valid_factor(db, scope="Scope 1", source_name="Diesel", unit="KL", activity_date=date(2023, 6, 1))
        current = get_valid_factor(db, scope="Scope 1", source_name="Diesel", unit="KL", activity_date=date(2024, 6, 1))

        assert historical.version == "2023-expired"
        assert current.version == "2024-active"
        assert calculate_kgco2e(10, historical) == 26000
        assert calculate_kgco2e(10, current) == 28000
