#!/bin/bash
# Install NLP dependencies for gap generation
# Run inside ai-chatbot-rag container

echo "📦 Installing NLP dependencies for Song Learning gap generation..."

# Install Python packages
pip install spacy wordfreq better-profanity

# Download spaCy English model
echo "⬇️  Downloading spaCy English model (en_core_web_sm)..."
python -m spacy download en_core_web_sm

echo "✅ NLP dependencies installed successfully!"
echo ""
echo "Installed packages:"
pip list | grep -E "(spacy|wordfreq|better-profanity)"

echo ""
echo "spaCy model verification:"
python -c "import spacy; nlp = spacy.load('en_core_web_sm'); print(f'✅ Model loaded: {nlp.meta[\"name\"]} v{nlp.meta[\"version\"]}')"
