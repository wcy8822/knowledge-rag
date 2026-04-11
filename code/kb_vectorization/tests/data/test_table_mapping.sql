-- 数据表映射关系

-- 商户基本信息表
CREATE TABLE dim_merchant (
    merchant_id BIGINT PRIMARY KEY,
    merchant_name VARCHAR(100),
    merchant_type VARCHAR(20),
    province VARCHAR(50),
    city VARCHAR(50),
    create_time DATETIME,
    update_time DATETIME
);

-- 交易流水表
CREATE TABLE fact_transaction (
    transaction_id BIGINT PRIMARY KEY,
    merchant_id BIGINT,
    transaction_amount DECIMAL(18,2),
    transaction_time DATETIME,
    pay_type VARCHAR(20),
    INDEX idx_merchant_id (merchant_id)
);

-- 映射关系
-- dim_merchant.merchant_id = fact_transaction.merchant_id
