-- 多中心系统数据库迁移脚本
-- 此脚本用于将现有单中心系统升级为多中心系统

-- 1. 创建中心表
CREATE TABLE IF NOT EXISTS centers (
    id INT PRIMARY KEY AUTO_INCREMENT,
    center_code VARCHAR(20) UNIQUE NOT NULL,
    center_name VARCHAR(100) NOT NULL,
    is_main_center BOOLEAN DEFAULT FALSE,
    contact_person VARCHAR(100),
    contact_phone VARCHAR(20),
    contact_email VARCHAR(100),
    address VARCHAR(255),
    is_active BOOLEAN DEFAULT TRUE,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_center_code (center_code),
    INDEX idx_is_active (is_active)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 2. 创建邀请码表
CREATE TABLE IF NOT EXISTS invitation_codes (
    id INT PRIMARY KEY AUTO_INCREMENT,
    code VARCHAR(50) UNIQUE NOT NULL,
    center_id INT NOT NULL,
    role VARCHAR(20) NOT NULL,
    max_uses INT DEFAULT 1,
    used_count INT DEFAULT 0,
    is_active BOOLEAN DEFAULT TRUE,
    expires_at DATETIME,
    created_by INT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_code (code),
    INDEX idx_center_id (center_id),
    INDEX idx_is_active (is_active)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 3. 修改用户表
-- 添加 center_id 字段
ALTER TABLE users
ADD COLUMN center_id INT NULL AFTER role,
ADD INDEX idx_center_id (center_id);

-- 修改 role 枚举值（如果使用ENUM类型）
-- 注意：如果当前使用的是VARCHAR类型，可以跳过此步骤
-- ALTER TABLE users
-- MODIFY COLUMN role ENUM('researcher', 'qc', 'center_admin', 'main_admin') DEFAULT 'researcher';

-- 4. 修改患者表
-- 添加 center_id 字段
ALTER TABLE patients
ADD COLUMN center_id INT NULL AFTER center_code,
ADD INDEX idx_center_id (center_id);

-- 5. 插入默认主中心
INSERT INTO centers (center_code, center_name, is_main_center, is_active)
VALUES ('CHN-001', '总中心', TRUE, TRUE)
ON DUPLICATE KEY UPDATE center_name = center_name;

-- 6. 插入示例分中心
INSERT INTO centers (center_code, center_name, is_main_center, is_active)
VALUES
    ('CHN-017', '北京分中心', FALSE, TRUE),
    ('CHN-018', '上海分中心', FALSE, TRUE),
    ('CHN-019', '广州分中心', FALSE, TRUE)
ON DUPLICATE KEY UPDATE center_name = center_name;

-- 7. 更新现有用户的 center_id（将所有用户分配到主中心）
UPDATE users
SET center_id = (SELECT id FROM centers WHERE is_main_center = TRUE LIMIT 1)
WHERE center_id IS NULL;

-- 8. 更新现有管理员角色
-- 将原来的 'admin' 角色改为 'main_admin'
UPDATE users
SET role = 'main_admin'
WHERE role = 'admin';

-- 9. 更新现有患者的 center_id
-- 方法1：根据 center_code 匹配
UPDATE patients p
INNER JOIN centers c ON p.center_code = c.center_code
SET p.center_id = c.id
WHERE p.center_id IS NULL;

-- 方法2：如果没有匹配的，分配到主中心
UPDATE patients
SET center_id = (SELECT id FROM centers WHERE is_main_center = TRUE LIMIT 1)
WHERE center_id IS NULL;

-- 10. 将 center_id 设为 NOT NULL（在确保所有数据都有 center_id 后）
-- ALTER TABLE users
-- MODIFY COLUMN center_id INT NOT NULL;

-- ALTER TABLE patients
-- MODIFY COLUMN center_id INT NOT NULL;

-- 11. 添加外键约束（可选，建议在生产环境中添加）
-- ALTER TABLE users
-- ADD CONSTRAINT fk_users_center
-- FOREIGN KEY (center_id) REFERENCES centers(id) ON DELETE RESTRICT;

-- ALTER TABLE patients
-- ADD CONSTRAINT fk_patients_center
-- FOREIGN KEY (center_id) REFERENCES centers(id) ON DELETE RESTRICT;

-- 12. 验证数据
SELECT '=== 中心列表 ===' AS info;
SELECT * FROM centers;

SELECT '=== 用户统计 ===' AS info;
SELECT c.center_name, u.role, COUNT(*) as count
FROM users u
LEFT JOIN centers c ON u.center_id = c.id
GROUP BY c.center_name, u.role;

SELECT '=== 患者统计 ===' AS info;
SELECT c.center_name, COUNT(*) as patient_count
FROM patients p
LEFT JOIN centers c ON p.center_id = c.id
GROUP BY c.center_name;

SELECT '=== 检查未分配中心的记录 ===' AS info;
SELECT 'users' as table_name, COUNT(*) as count FROM users WHERE center_id IS NULL
UNION ALL
SELECT 'patients' as table_name, COUNT(*) as count FROM patients WHERE center_id IS NULL;
