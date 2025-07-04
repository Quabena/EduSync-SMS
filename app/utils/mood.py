"""
Classroom mood analysis utility
"""

from textblob import TextBlob
from app.models import Student, Classroom, MoodEntry
from app import db
from datetime import datetime, timedelta


def analyze_sentiment(text):
    analysis = TextBlob(text)
    polarity = analysis.sentiment.polarity  # type: ignore

    if polarity > 0.3:
        return "positive", polarity
    elif polarity < -0.3:
        return "negative", polarity
    else:
        return "neutral", polarity


def record_classroom_mood(class_id, notes):
    # Analyzing overall sentiment
    sentiment, polarity = analyze_sentiment(notes)

    # Creating mood entry
    entry = MoodEntry(
        class_id=class_id,
        notes=notes,
        sentiment=sentiment,
        polarity=polarity,
        recorded_at=datetime.now(),
    )
    db.session.add(entry)
    db.session.commit()

    return entry


def get_classroom_mood(class_id, days=30):
    # Getting mood entries for the class
    cutoff = datetime.now() - timedelta(days=days)
    entries = (
        MoodEntry.query.filter(
            MoodEntry.class_id == class_id, MoodEntry.recorded_at >= cutoff
        )
        .order_by(MoodEntry.recorded_at.asc())
        .all()
    )

    # Preparing data for charting
    mood_data = []
    for entry in entries:
        mood_data.append(
            {
                "date": entry.recorded_at.strftime("%Y-%m-%d"),
                "sentiment": entry.sentiment,
                "polarity": entry.polarity,
                "notes": entry.notes,
            }
        )

    return mood_data
