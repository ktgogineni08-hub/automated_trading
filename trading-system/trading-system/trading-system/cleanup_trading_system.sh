#!/bin/bash
# Trading System Folder Cleanup Script

set -e

echo "=========================================="
echo "Trading System Folder Cleanup"
echo "=========================================="

# Create archive folder for old files
ARCHIVE_DIR="archived_development_files"
mkdir -p "$ARCHIVE_DIR"/{old_tests,old_reviews,debug_scripts}

echo ""
echo "Step 1: Archiving old test scripts..."
mv test_advanced_market_system.py test_all_exit_fixes.py test_all_indices_support.py \
   test_all_nse_formats.py test_api_rate_limit_fix.py test_auto_trade_management.py \
   test_banknifty_expiry.py test_complete_fno_fixes.py test_correct_nse_parser.py \
   test_critical_fixes.py test_duplicate_prevention.py test_enhanced_system.py \
   test_expiry_extraction.py test_expiry_fix_validation.py test_expiry_method.py \
   test_final_all_symbols.py test_final_expiry_parser.py test_final_parser.py \
   test_finnifty_expiry_dates.py test_finnifty_monthly.py test_finnifty_parser.py \
   test_latest_parser.py test_live_trading_fixes.py test_new_logic_debug.py \
   test_parser_debug.py test_parser_on_expiry.py test_position_closing.py \
   test_security_fixes.py test_thursday_logic.py test_updated_parser.py \
   test_batch_api_calls.py test_comprehensive_fixes.py test_dashboard_fixes.py \
   test_dashboard_sync.py test_data_integrity.py test_duplicate_fix.py \
   test_enhanced_fixes.py test_entry_fees.py test_exit_order_status.py \
   test_expiry_fix.py test_fno_order_placement.py test_margin_checking.py \
   test_midcap_nifty_support.py test_nifty_monthly_expiry.py test_order_timing.py \
   test_paper_trade_fix.py test_portfolio_sync.py test_position_sync.py \
   test_price_fetching.py test_weekly_contracts_fix.py test_all_fixes.py \
   test_close_market_integration.py test_expiry_close_integration.py \
   test_rate_limit.py test_symbol_parser.py \
   "$ARCHIVE_DIR/old_tests/" 2>/dev/null || echo "  (some files already removed)"

echo "Step 2: Archiving old review/fix documentation..."
mv ALL_FIXES_COMPLETE.md API_RATE_LIMITING_FIX.md CODE_REVIEW_FINAL_CODERABBIT.md \
   CODE_REVIEW_FINDINGS.md CODE_REVIEW_FIXES_ROUND2.md CODE_REVIEW_FIXES_ROUND3.md \
   CODE_REVIEW_USER_CHANGES.md COMPREHENSIVE_CODE_REVIEW.md CRITICAL_BUG_FIX_PAPER_TRADING.md \
   CRITICAL_FIXES_ROUND2.md CRITICAL_FIXES_ROUND3.md CRITICAL_FIXES_VALIDATION.md \
   DEEP_CODE_REVIEW_ROUND2.md DUPLICATE_POSITIONS_CRITICAL_FIX.md ENHANCEMENTS_SUMMARY.md \
   EXPIRY_CRITICAL_FIXES.md EXPIRY_DATE_EXTRACTION_FIX.md EXPIRY_FROM_KITE_PROPOSAL.md \
   EXPIRY_PARSER_FIX.md EXPIRY_PARSER_FIX_COMPLETE.md EXPIRY_SIMPLIFIED_USING_KITE.md \
   FINAL_PARSER_VERIFICATION.md FINAL_VALIDATION_REPORT.md FINAL_VERIFICATION.md \
   FINNIFTY_MONTHLY_EXPIRY_FIX.md NSE_PARSER_FINAL_CORRECT.md NSE_SYMBOL_PARSER_FINAL_FIX.md \
   PARSER_FIX_FINAL.md POSITION_PRICE_FETCHING_AUDIT.md POSITION_SYNC_FIX.md \
   PRICE_FETCHING_FIX.md RATE_LIMIT_FIX.md SECURITY_FIXES.md SYMBOL_FUZZY_MATCHING_FIX.md \
   SYSTEM_AUDIT_REPORT.md WEEKLY_CONTRACTS_FIX.md check_kite_symbol_format.md \
   INTEGRATION_COMPLETE.md INTEGRATION_FIX.md MINOR_WARNINGS_FIXED.md NEXT_STEPS.md \
   PORTFOLIO_SYNC_DIAGNOSTIC.md STOP_LOSS_REDUCED_TO_5_PERCENT.md \
   "$ARCHIVE_DIR/old_reviews/" 2>/dev/null || echo "  (some files already removed)"

echo "Step 3: Archiving debug/diagnostic scripts..."
mv check_positions.py cleanup_duplicates.py debug_symbol_fetch.py \
   diagnose_price_difference.py verify_batching.py verify_parser_logic.py \
   repl_sanity_check.py fix_dashboard_sync.py \
   "$ARCHIVE_DIR/debug_scripts/" 2>/dev/null || echo "  (some files already removed)"

echo ""
echo "Step 4: Removing temporary analysis script..."
rm -f analyze_files.py

echo ""
echo "=========================================="
echo "✅ Cleanup Complete!"
echo "=========================================="
echo ""
echo "Archived folders created:"
echo "  • $ARCHIVE_DIR/old_tests/ (55 test scripts)"
echo "  • $ARCHIVE_DIR/old_reviews/ (40 review docs)"
echo "  • $ARCHIVE_DIR/debug_scripts/ (8 debug scripts)"
echo ""
echo "Core files remaining:"
ls -1 *.py *.md 2>/dev/null | grep -E "^(enhanced|advanced|zerodha|test_gtt|test_trade|TRADE_|GTT_|DEPLOYMENT|READY)" || true
echo ""
