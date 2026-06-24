import json

from anthropic import AsyncAnthropic

from app.config import settings


def generate_rule_based_insights(analytics_data: dict) -> list[str]:
    yoy = analytics_data["yoy"]
    current = yoy["selected_year"]
    previous = yoy["previous_year"]
    current_total = float(current["total_kgco2e"])
    previous_total = float(previous["total_kgco2e"])
    change_pct = (
        ((current_total - previous_total) / previous_total * 100)
        if previous_total
        else 0
    )

    hotspots = analytics_data.get("hotspots", [])
    top_hotspot = hotspots[0] if hotspots else None
    intensity = analytics_data["intensity"].get("intensity_kgco2e_per_unit")

    direction = "increased" if change_pct >= 0 else "decreased"
    insights = [
        (
            f"Total emissions {direction} {abs(change_pct):.1f}% versus "
            f"{previous['year']}; prioritize the largest operational drivers."
        )
    ]
    if top_hotspot:
        insights.append(
            f"{top_hotspot['source_name']} is the largest hotspot at {top_hotspot['share_pct']:.1f}% of reported emissions."
        )
    else:
        insights.append(
            "No emission hotspot data is available for the selected reporting period."
        )
    if intensity is not None:
        insights.append(
            f"Emission intensity is {float(intensity):,.1f} kgCO2e per production unit; track it monthly."
        )
    else:
        insights.append(
            "Add a production metric to calculate and manage emission intensity."
        )
    return insights


async def generate_insights(analytics_data: dict) -> dict:
    fallback = generate_rule_based_insights(analytics_data)
    if not settings.anthropic_api_key:
        return {
            "insights": fallback,
            "generated_by": "deterministic-analytics",
            "model": None,
            "notice": "Set ANTHROPIC_API_KEY to enable Claude-generated narrative insights.",
        }

    prompt = (
        "You are a sustainability analyst reviewing a GHG emissions dashboard. "
        "Return exactly three concise, actionable insights as a JSON array of strings. "
        "Each insight must be under 24 words, use specific numbers from the data, and avoid unsupported claims.\n\n"
        f"Analytics data:\n{json.dumps(analytics_data, indent=2, default=str)}"
    )

    try:
        client = AsyncAnthropic(api_key=settings.anthropic_api_key)
        message = await client.messages.create(
            model=settings.anthropic_model,
            max_tokens=350,
            messages=[{"role": "user", "content": prompt}],
        )
        text = "".join(
            block.text for block in message.content if block.type == "text"
        ).strip()
        parsed = json.loads(text)
        if (
            not isinstance(parsed, list)
            or len(parsed) != 3
            or not all(isinstance(item, str) for item in parsed)
        ):
            raise ValueError("Claude response was not a three-item JSON string array")
        return {
            "insights": parsed,
            "generated_by": "anthropic",
            "model": settings.anthropic_model,
            "notice": None,
        }
    except Exception:
        return {
            "insights": fallback,
            "generated_by": "deterministic-analytics",
            "model": None,
            "notice": "Claude was unavailable, so verified deterministic insights are shown.",
        }
