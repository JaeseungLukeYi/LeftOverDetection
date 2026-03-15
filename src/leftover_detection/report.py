from __future__ import annotations

from datetime import date


def build_waste_report(
    category_rows: list[tuple[str, float, int]],
    top_food_rows: list[tuple[str, float, int]],
    start_date: date,
    end_date: date,
) -> str:
    if not category_rows:
        return (
            f"Food waste analysis for {start_date.isoformat()} to {end_date.isoformat()}\n"
            "No tray records were found for this period."
        )

    lines = [f"Food waste analysis for {start_date.isoformat()} to {end_date.isoformat()}", ""]
    lines.append("Highest-waste categories:")
    for category, avg_leftover, sample_count in category_rows[:5]:
        lines.append(f"- {category}: {avg_leftover:.1f}% avg leftover ({sample_count} records)")

    lines.append("")
    lines.append("Top individual foods by leftover rate:")
    for food_item, avg_leftover, sample_count in top_food_rows:
        lines.append(f"- {food_item}: {avg_leftover:.1f}% avg leftover ({sample_count} records)")

    if len(category_rows) >= 2:
        highest = category_rows[0]
        lowest = category_rows[-1]
        lines.append("")
        lines.append(
            "Summary insight: "
            f"{highest[0]} shows the highest average leftover ({highest[1]:.1f}%), "
            f"while {lowest[0]} is lowest ({lowest[1]:.1f}%)."
        )

    return "\n".join(lines)
