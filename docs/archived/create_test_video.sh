#!/bin/bash

# =============================================================================
# Create Test Video Subsets
# =============================================================================
# This script creates shorter test videos for quick SAHI evaluation
#
# Usage:
#   ./create_test_video.sh assets/glorieta_normal.mp4 30
#   ./create_test_video.sh assets/patria_acueducto.mp4 60
#
# Arguments:
#   $1 - Input video file
#   $2 - Duration in seconds (default: 30)
#
# Output:
#   Creates {basename}_test_{duration}s.mp4 in assets/ directory
# =============================================================================

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Check if ffmpeg is installed
if ! command -v ffmpeg &> /dev/null; then
    echo -e "${RED}❌ Error: ffmpeg is not installed${NC}"
    echo "Install with: brew install ffmpeg"
    exit 1
fi

# Check arguments
if [ -z "$1" ]; then
    echo -e "${RED}❌ Error: No input file specified${NC}"
    echo "Usage: $0 <input_video> [duration_seconds]"
    echo "Example: $0 assets/glorieta_normal.mp4 30"
    exit 1
fi

INPUT_VIDEO="$1"
DURATION="${2:-30}"  # Default 30 seconds

# Check if input file exists
if [ ! -f "$INPUT_VIDEO" ]; then
    echo -e "${RED}❌ Error: Input file not found: $INPUT_VIDEO${NC}"
    exit 1
fi

# Get basename and directory
BASENAME=$(basename "$INPUT_VIDEO" | sed 's/\.[^.]*$//')
DIRNAME=$(dirname "$INPUT_VIDEO")
OUTPUT_VIDEO="${DIRNAME}/${BASENAME}_test_${DURATION}s.mp4"

echo -e "${BLUE}════════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}🎬 Creating Test Video Subset${NC}"
echo -e "${BLUE}════════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}Input:${NC}    $INPUT_VIDEO"
echo -e "${GREEN}Duration:${NC} ${DURATION}s"
echo -e "${GREEN}Output:${NC}   $OUTPUT_VIDEO"
echo ""

# Get video info
echo -e "${YELLOW}📊 Analyzing input video...${NC}"
VIDEO_INFO=$(ffprobe -v error -show_entries format=duration,size,bit_rate -show_entries stream=width,height,r_frame_rate -of default=noprint_wrappers=1 "$INPUT_VIDEO")

echo "$VIDEO_INFO" | grep -E "(width|height|duration|size|bit_rate|r_frame_rate)"
echo ""

# Extract subset
echo -e "${YELLOW}✂️  Extracting ${DURATION}s from video...${NC}"

ffmpeg -i "$INPUT_VIDEO" \
    -t "$DURATION" \
    -c:v libx264 \
    -preset fast \
    -crf 23 \
    -c:a aac \
    -b:a 128k \
    -y \
    "$OUTPUT_VIDEO" 2>&1 | grep -E "(frame=|size=|time=|bitrate=|speed=)" || true

echo ""

# Verify output
if [ -f "$OUTPUT_VIDEO" ]; then
    OUTPUT_SIZE=$(du -h "$OUTPUT_VIDEO" | cut -f1)
    echo -e "${GREEN}✅ Test video created successfully!${NC}"
    echo -e "${GREEN}   File:${NC} $OUTPUT_VIDEO"
    echo -e "${GREEN}   Size:${NC} $OUTPUT_SIZE"
    echo ""
    echo -e "${BLUE}💡 Quick test commands:${NC}"
    echo -e "   ${YELLOW}# Standard YOLO:${NC}"
    echo -e "   python main.py --mode roundabout-test --video \"$OUTPUT_VIDEO\""
    echo ""
    echo -e "   ${YELLOW}# SAHI Enhanced:${NC}"
    echo -e "   python main_sahi.py --mode roundabout-test --video \"$OUTPUT_VIDEO\""
    echo ""
    echo -e "   ${YELLOW}# Comparison:${NC}"
    echo -e "   python compare_methods.py --video \"$OUTPUT_VIDEO\""
    echo -e "${BLUE}════════════════════════════════════════════════════════════${NC}"
else
    echo -e "${RED}❌ Error: Failed to create test video${NC}"
    exit 1
fi
