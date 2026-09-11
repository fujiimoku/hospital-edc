-- 多实例共享 MySQL 的初始化脚本（MySQL 容器首次启动时自动执行）
-- 每个项目实例一个独立库，数据物理隔离。
CREATE DATABASE IF NOT EXISTS edc_project_a CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE DATABASE IF NOT EXISTS edc_project_b CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
