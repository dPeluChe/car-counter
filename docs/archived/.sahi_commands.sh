#!/bin/bash
# ============================================================================
# SAHI Commands Cheat Sheet
# ============================================================================
# Quick reference of common SAHI commands for copy-paste
# Uncomment the command you want to run and execute this file
# ============================================================================

# ----------------------------------------------------------------------------
# INSTALLATION & SETUP
# ----------------------------------------------------------------------------

# Install all dependencies including SAHI
# pip install -r requirements.txt

# Verify SAHI installation
# python -c "import sahi; print(f'SAHI {sahi.__version__} installed successfully')"

# Check if CUDA is available (for GPU acceleration)
# python -c "import torch; print(f'CUDA available: {torch.cuda.is_available()}')"


# ----------------------------------------------------------------------------
# CREATE TEST VIDEOS (Quick iterations)
# ----------------------------------------------------------------------------

# Create 30-second test video from glorieta
# ./create_test_video.sh assets/glorieta_normal.mp4 30

# Create 60-second test video
# ./create_test_video.sh assets/glorieta_normal.mp4 60

# Create 15-second quick test
# ./create_test_video.sh assets/glorieta_caballos.MOV 15


# ----------------------------------------------------------------------------
# BASIC SAHI EXECUTION (Roundabout Test Mode)
# ----------------------------------------------------------------------------

# Standard configuration (balanced)
# python main_sahi.py \
#     --mode roundabout-test \
#     --video assets/glorieta_normal_test_30s.mp4 \
#     --slice-height 512 \
#     --slice-width 512 \
#     --overlap 0.2

# High precision (slower, better detection)
# python main_sahi.py \
#     --mode roundabout-test \
#     --video assets/glorieta_normal_test_30s.mp4 \
#     --slice-height 384 \
#     --slice-width 384 \
#     --overlap 0.25 \
#     --conf-threshold 0.2

# Fast mode (larger tiles)
# python main_sahi.py \
#     --mode roundabout-test \
#     --video assets/glorieta_normal_test_30s.mp4 \
#     --slice-height 768 \
#     --slice-width 768 \
#     --overlap 0.15


# ----------------------------------------------------------------------------
# SAHI WITH BENCHMARKING
# ----------------------------------------------------------------------------

# Run with benchmarking and FPS display
# python main_sahi.py \
#     --mode roundabout-test \
#     --video assets/glorieta_normal_test_30s.mp4 \
#     --benchmark \
#     --show-fps

# GPU accelerated with benchmarking
# python main_sahi.py \
#     --mode roundabout-test \
#     --video assets/glorieta_normal_test_30s.mp4 \
#     --device cuda \
#     --benchmark \
#     --show-fps


# ----------------------------------------------------------------------------
# STREET MODE (Counting with lines)
# ----------------------------------------------------------------------------

# Bidirectional counting
# python main_sahi.py \
#     --mode street \
#     --video assets/patria_acueducto.mp4 \
#     --directions 2 \
#     --line-y 0.4 \
#     --line-y2 0.6 \
#     --slice-height 512 \
#     --slice-width 512 \
#     --overlap 0.2

# Single line counting
# python main_sahi.py \
#     --mode street \
#     --video assets/test_2.mp4 \
#     --directions 1 \
#     --line-y 0.5 \
#     --slice-height 512 \
#     --slice-width 512


# ----------------------------------------------------------------------------
# COMPARISON TOOLS
# ----------------------------------------------------------------------------

# Compare Standard YOLO vs SAHI (automatic)
# python compare_methods.py \
#     --video assets/glorieta_normal_test_30s.mp4 \
#     --output benchmarks/comparison_$(date +%Y%m%d_%H%M%S).json

# Run only SAHI (skip standard)
# python compare_methods.py \
#     --video assets/glorieta_normal_test_30s.mp4 \
#     --skip-standard

# Run only Standard YOLO (skip SAHI)
# python compare_methods.py \
#     --video assets/glorieta_normal_test_30s.mp4 \
#     --skip-sahi

# Custom slice size in comparison
# python compare_methods.py \
#     --video assets/glorieta_normal_test_30s.mp4 \
#     --slice-size 384 \
#     --overlap 0.25


# ----------------------------------------------------------------------------
# FULL VIDEO PROCESSING (Long running)
# ----------------------------------------------------------------------------

# Process full video (WARNING: Can take hours!)
# python main_sahi.py \
#     --mode roundabout-test \
#     --video assets/glorieta_normal.mp4 \
#     --slice-height 512 \
#     --slice-width 512 \
#     --overlap 0.2 \
#     --benchmark \
#     --show-fps

# Full video with GPU
# python main_sahi.py \
#     --mode roundabout-test \
#     --video assets/glorieta_caballos.MOV \
#     --device cuda \
#     --slice-height 512 \
#     --slice-width 512 \
#     --benchmark


# ----------------------------------------------------------------------------
# BATCH PROCESSING (Multiple videos)
# ----------------------------------------------------------------------------

# Process all glorieta videos with same config
# for video in assets/glorieta_*.{mp4,MOV}; do
#     echo "Processing $video..."
#     python main_sahi.py \
#         --mode roundabout-test \
#         --video "$video" \
#         --slice-height 512 \
#         --slice-width 512 \
#         --benchmark
# done

# Create test videos for all glorietas
# for video in assets/glorieta_*.{mp4,MOV}; do
#     ./create_test_video.sh "$video" 30
# done


# ----------------------------------------------------------------------------
# PARAMETER TUNING (Find optimal configuration)
# ----------------------------------------------------------------------------

# Test different slice sizes
# for size in 256 384 512 768 1024; do
#     echo "Testing slice size: ${size}x${size}"
#     python main_sahi.py \
#         --video assets/glorieta_normal_test_30s.mp4 \
#         --slice-height $size \
#         --slice-width $size \
#         --benchmark
# done

# Test different overlap ratios
# for overlap in 0.1 0.2 0.3; do
#     echo "Testing overlap: $overlap"
#     python main_sahi.py \
#         --video assets/glorieta_normal_test_30s.mp4 \
#         --slice-height 512 \
#         --slice-width 512 \
#         --overlap $overlap \
#         --benchmark
# done

# Test different confidence thresholds
# for conf in 0.15 0.2 0.25 0.3; do
#     echo "Testing confidence: $conf"
#     python main_sahi.py \
#         --video assets/glorieta_normal_test_30s.mp4 \
#         --conf-threshold $conf \
#         --benchmark
# done


# ----------------------------------------------------------------------------
# VIEW RESULTS
# ----------------------------------------------------------------------------

# Open output videos
# open result.mp4           # Standard YOLO
# open result_sahi.mp4      # SAHI enhanced

# View benchmark results
# cat benchmarks/sahi_results.txt
# cat benchmarks/comparison.json | jq '.'


# ----------------------------------------------------------------------------
# CLEANUP
# ----------------------------------------------------------------------------

# Remove all test videos
# rm -f assets/*_test_*.mp4

# Remove all result videos
# rm -f result*.mp4

# Clean benchmarks
# rm -rf benchmarks/*.txt benchmarks/*.json


# ============================================================================
# RECOMMENDED WORKFLOW FOR FIRST TIME
# ============================================================================

echo "=========================================="
echo "🚀 SAHI First Time Setup & Test"
echo "=========================================="
echo ""
echo "1. Install dependencies:"
echo "   pip install -r requirements.txt"
echo ""
echo "2. Create test video (30s):"
echo "   ./create_test_video.sh assets/glorieta_normal.mp4 30"
echo ""
echo "3. Run comparison:"
echo "   python compare_methods.py --video assets/glorieta_normal_test_30s.mp4"
echo ""
echo "4. View results:"
echo "   open result.mp4"
echo "   open result_sahi.mp4"
echo "   cat benchmarks/comparison.json"
echo ""
echo "=========================================="
echo "For detailed docs, see:"
echo "  - QUICKSTART_SAHI.md (quick guide)"
echo "  - SAHI.md (technical docs)"
echo "=========================================="
