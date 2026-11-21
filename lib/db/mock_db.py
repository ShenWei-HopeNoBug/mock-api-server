# -*- coding: utf-8 -*-
from typing import List

from app_types.db_types import ApiData, ApiQuery

from .api_data import ApiDataMixin
from .base import BaseSQLiteDB
from .constants import CURRENT_SCHEMA_VERSION
from .static_data import StaticDataMixin
from .test_group import TestGroupMixin
from .variants import ApiResponseVariantMixin


class MockDB(BaseSQLiteDB, ApiDataMixin, StaticDataMixin, ApiResponseVariantMixin, TestGroupMixin):
  """
  SQLite 数据访问层，封装 api_data / static_data / api_response_variants / test_group 的 CRUD 操作

  使用 WAL 模式 + autocommit，事务由 _transaction 上下文管理器显式控制。
  线程安全：通过 threading.Lock 保护所有读写操作。
  """

  _schema_version = CURRENT_SCHEMA_VERSION

  def _fetch_variants(self, api_id: str) -> list:
    """覆写 ApiDataMixin._fetch_variants hook，委托给 ApiResponseVariantMixin.get_variants_by_api_id

    MockDB 作为组合根，在此显式连接两个 Mixin 的能力，消除 ApiDataMixin 对 ApiResponseVariantMixin 的隐式依赖
    """
    return self.get_variants_by_api_id(api_id)

  def _fetch_group_items(self, group_id: str) -> List[ApiData]:
    """覆写 TestGroupMixin._fetch_group_items hook，委托给 ApiDataMixin.get_api_list

    组内条目 = type='TEST_GROUP' 且 group_id 匹配的 api_data 行，按 created_at/id 正序返回
    """
    return self.get_api_list(ApiQuery(api_type='TEST_GROUP', group_id=group_id))

  def _migrate_schema(self, from_version: int, to_version: int) -> None:
    """执行 schema 版本迁移，调度各 Mixin 的表级迁移逻辑（整体一个事务）"""
    with self._transaction():
      self._migrate_api(from_version, to_version)
      self._migrate_static(from_version, to_version)
      self._migrate_variant(from_version, to_version)
      self._migrate_test_group(from_version, to_version)
      super()._migrate_schema(from_version, to_version)
