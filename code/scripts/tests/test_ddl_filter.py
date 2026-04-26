#!/usr/bin/env python3
"""loki_ddl_filter 单元测试 (D.2)"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from loki_ddl_filter import (  # noqa: E402
    filter_pairs,
    is_excluded_db,
    is_excluded_table,
    is_excluded_table_name,
)


class TestIsExcludedDb:
    def test_archive_prefix(self):
        assert is_excluded_db("_archive")
        assert is_excluded_db("_archive_old")

    def test_trash_prefix(self):
        assert is_excluded_db("_trash")

    def test_staging_prefix(self):
        assert is_excluded_db("_staging")

    def test_normal_db(self):
        assert not is_excluded_db("data_manager_db")
        assert not is_excluded_db("gas_dw")
        assert not is_excluded_db("am_bi_dev")
        assert not is_excluded_db("priceDB")

    def test_empty(self):
        assert not is_excluded_db("")
        assert not is_excluded_db(None)


class TestIsExcludedTableName:
    def test_backup_suffix(self):
        assert is_excluded_table_name("tag_master_backup")
        assert is_excluded_table_name("dm_backup_history")

    def test_backup_with_date(self):
        assert is_excluded_table_name("tag_master_backup_20251124")
        assert is_excluded_table_name("fgw_adjust_history_backup_20260310_165708")

    def test_pure_date_suffix_not_excluded(self):
        # 仅日期后缀（无 _backup 等关键词）不命中，保留
        assert not is_excluded_table_name("ui_uir_visit_records_20251124_214858")

    def test_bak_suffix(self):
        assert is_excluded_table_name("tag_master_bak")
        assert is_excluded_table_name("config_bak_v1")

    def test_old_suffix(self):
        assert is_excluded_table_name("tag_master_old")

    def test_staging_suffix(self):
        assert is_excluded_table_name("station_tag_merge_staging")
        assert is_excluded_table_name("brand_import_staging")

    def test_tmp_temp_suffix(self):
        assert is_excluded_table_name("scratch_tmp")
        assert is_excluded_table_name("ad_temp")

    def test_normal_business_table(self):
        assert not is_excluded_table_name("dwm_gas_trd_indicators_di")
        assert not is_excluded_table_name("v_merchant_profile_latest_di")
        assert not is_excluded_table_name("tag_master")

    def test_avoid_false_positive_prefix_backup(self):
        # backup_strategy_log 是合法业务表（前缀 backup_ 不在结尾）
        assert not is_excluded_table_name("backup_strategy_log")

    def test_avoid_false_positive_old_inside(self):
        # gold_record / scaffolding 之类不命中
        assert not is_excluded_table_name("gold_record")
        assert not is_excluded_table_name("scaffolding")

    def test_empty(self):
        assert not is_excluded_table_name("")
        assert not is_excluded_table_name(None)


class TestIsExcludedTable:
    def test_excluded_via_db(self):
        assert is_excluded_table("_archive", "any_business_table")

    def test_excluded_via_table(self):
        assert is_excluded_table("data_manager_db", "tag_master_backup")

    def test_both_clean(self):
        assert not is_excluded_table("data_manager_db", "tag_master")

    def test_real_world_samples(self):
        # 来自现场实际 ddl 集合采样
        assert is_excluded_table("_archive", "data_manager_db__backup_ui_uir_visit_records_20251124_214858")
        assert is_excluded_table("_archive", "data_manager_db__dm_backup_history")
        assert is_excluded_table("_archive", "data_manager_db__brand_import_staging")
        assert not is_excluded_table("data_manager_db", "v_merchant_profile_latest_di")
        assert not is_excluded_table("gas_dw", "dwm_gas_trd_profit_store_di")


class TestFilterPairs:
    def test_filters_excluded(self):
        pairs = [
            ("data_manager_db", "tag_master", "comment1"),
            ("_archive", "junk", "comment2"),
            ("data_manager_db", "tag_master_backup", "comment3"),
            ("gas_dw", "dwm_gas_trd_indicators_di", "comment4"),
        ]
        out = filter_pairs(pairs)
        assert len(out) == 2
        assert out[0][1] == "tag_master"
        assert out[1][1] == "dwm_gas_trd_indicators_di"

    def test_skip_short_tuples(self):
        pairs = [("only_one_field",), ("data_manager_db", "tag_master")]
        out = filter_pairs(pairs)
        assert len(out) == 1

    def test_empty(self):
        assert filter_pairs([]) == []
