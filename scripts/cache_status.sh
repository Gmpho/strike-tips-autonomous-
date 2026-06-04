#!/bin/bash

# Cache Status Script for Strike Tips Racing Bot
# Provides a quick overview of cache sizes and health

BASE_DIR="/home/giftmpho/Kimi_Agent_Strike Tips Racing Bot"
DATA_DIR="$BASE_DIR/data"

echo "=== Strike Tips Racing Bot Cache Status ==="
echo "Timestamp: $(date)"
echo ""

# Intelligence Cache
INTEL_CACHE="$DATA_DIR/intelligence_cache"
if [ -d "$INTEL_CACHE" ]; then
    intel_size=$(du -sh "$INTEL_CACHE" | cut -f1)
    intel_count=$(find "$INTEL_CACHE" -type f | wc -l)
    echo "🧠 Intelligence Cache:"
    echo "   Size: $intel_size"
    echo "   Files: $intel_count"
    # Show oldest and newest file times for TTL context
    if [ "$intel_count" -gt 0 ]; then
        oldest=$(find "$INTEL_CACHE" -type f -printf '%T+ %p\n' | sort | head -1 | cut -d' ' -f1)
        newest=$(find "$INTEL_CACHE" -type f -printf '%T+ %p\n' | sort | tail -1 | cut -d' ' -f1)
        echo "   Oldest: $oldest"
        echo "   Newest: $newest"
    fi
    echo ""
else
    echo "🧠 Intelligence Cache: Not found"
    echo ""
fi

# Alert History
ALERT_HISTORY="$DATA_DIR/alert_history.json"
if [ -f "$ALERT_HISTORY" ]; then
    alert_size=$(du -h "$ALERT_HISTORY" | cut -f1)
    alert_lines=$(wc -l < "$ALERT_HISTORY")
    echo "🚨 Alert History:"
    echo "   Size: $alert_size"
    echo "   Lines (alerts): $alert_lines"
    # Check for rotated files
    rotated=$(ls -la "$DATA_DIR"/alert_history.json.* 2>/dev/null | wc -l)
    if [ "$rotated" -gt 0 ]; then
        echo "   Rotated archives: $rotated"
    fi
    echo ""
else
    echo "🚨 Alert History: Not found"
    echo ""
fi

# PDF Cache
PDF_CACHE="$DATA_DIR/pdf_cache"
if [ -d "$PDF_CACHE" ]; then
    pdf_size=$(du -sh "$PDF_CACHE" | cut -f1)
    pdf_count=$(find "$PDF_CACHE" -type f | wc -l)
    echo "📄 PDF Cache:"
    echo "   Size: $pdf_size"
    echo "   Files: $pdf_count"
    echo ""
else
    echo "📄 PDF Cache: Not found"
    echo ""
fi

# Chroma DB (Vector Memory)
CHROMA="$DATA_DIR/chroma"
if [ -d "$CHROMA" ]; then
    chroma_size=$(du -sh "$CHROMA" | cut -f1)
    chroma_count=$(find "$CHROMA" -type f | wc -l)
    echo "🧠 Chroma DB (Memory):"
    echo "   Size: $chroma_size"
    echo "   Files: $chroma_count"
    echo ""
else
    echo "🧠 Chroma DB (Memory): Not found"
    echo ""
fi

# Market Snapshot (current)
SNAPSHOT="$DATA_DIR/market_snapshot_latest.json"
if [ -f "$SNAPSHOT" ]; then
    snap_size=$(du -h "$SNAPSHOT" | cut -f1)
    echo "📸 Market Snapshot:"
    echo "   Size: $snap_size"
    echo ""
else
    echo "📸 Market Snapshot: Not found"
    echo ""
fi

echo "=== End of Cache Status ==="