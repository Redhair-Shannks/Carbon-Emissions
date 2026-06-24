from datetime import date

from fastapi import HTTPException
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models import EmissionFactor


def get_valid_factor(
    db: Session,
    *,
    scope: str,
    source_name: str,
    unit: str,
    activity_date: date,
) -> EmissionFactor:
    stmt = (
        select(EmissionFactor)
        .where(
            func.lower(EmissionFactor.scope) == scope.lower(),
            func.lower(EmissionFactor.source_name) == source_name.lower(),
            func.lower(EmissionFactor.unit) == unit.lower(),
            EmissionFactor.valid_from <= activity_date,
            or_(
                EmissionFactor.valid_to.is_(None),
                EmissionFactor.valid_to >= activity_date,
            ),
        )
        .order_by(EmissionFactor.valid_from.desc(), EmissionFactor.id.desc())
    )
    factor = db.scalars(stmt).first()
    if not factor:
        raise HTTPException(
            status_code=404,
            detail=(
                "No emission factor is valid for this scope/source/unit/date. "
                "Check master data or choose a date covered by a factor version."
            ),
        )
    return factor


def calculate_kgco2e(quantity: float, factor: EmissionFactor) -> float:
    return round(quantity * factor.factor_kgco2e_per_unit, 6)
