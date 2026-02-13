#!/bin/bash

# Add test memories with emotion annotations

echo "Adding test memories..."

# Memory 1: Happy event
no_proxy=localhost curl -X POST "http://localhost:5000/api/v1/memories/" \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "demo_user",
    "content": "Had an amazing day at the beach with friends. The weather was perfect!",
    "memory_type": "episodic",
    "metadata": {
      "emotion": {
        "valence": 0.8,
        "arousal": 0.7,
        "label": "happy"
      },
      "importance": 8
    }
  }'

echo ""

# Memory 2: Work fact
no_proxy=localhost curl -X POST "http://localhost:5000/api/v1/memories/" \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "demo_user",
    "content": "I work at Google as a software engineer specializing in Python and AI.",
    "memory_type": "fact",
    "metadata": {
      "emotion": {
        "valence": 0.5,
        "arousal": 0.4,
        "label": "neutral"
      },
      "importance": 7
    }
  }'

echo ""

# Memory 3: Preference
no_proxy=localhost curl -X POST "http://localhost:5000/api/v1/memories/" \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "demo_user",
    "content": "I prefer Python over JavaScript for backend development.",
    "memory_type": "preference",
    "metadata": {
      "emotion": {
        "valence": 0.3,
        "arousal": 0.3,
        "label": "content"
      },
      "importance": 5
    }
  }'

echo ""

# Memory 4: Sad event
no_proxy=localhost curl -X POST "http://localhost:5000/api/v1/memories/" \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "demo_user",
    "content": "My project got cancelled today. Feeling disappointed about it.",
    "memory_type": "episodic",
    "metadata": {
      "emotion": {
        "valence": -0.6,
        "arousal": 0.5,
        "label": "sad"
      },
      "importance": 6
    }
  }'

echo ""

# Memory 5: Insight
no_proxy=localhost curl -X POST "http://localhost:5000/api/v1/memories/" \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "demo_user",
    "content": "User shows strong interest in AI and machine learning topics. Often asks about latest developments.",
    "memory_type": "insight",
    "metadata": {
      "emotion": {
        "valence": 0.4,
        "arousal": 0.6,
        "label": "interested"
      },
      "importance": 9
    }
  }'

echo ""
echo "✅ Test data added successfully!"
