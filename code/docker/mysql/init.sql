-- ============================================
-- MySQL 初始化脚本
-- Docker 首次启动时自动执行
-- ============================================

-- 设置字符集
SET NAMES utf8mb4;
SET CHARACTER SET utf8mb4;

-- 确保数据库存在
CREATE DATABASE IF NOT EXISTS enterprise_qa
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

USE enterprise_qa;

-- 注意：表结构由 Alembic 迁移管理，此文件仅做基础保障
-- alembic upgrade head 会创建所有业务表
