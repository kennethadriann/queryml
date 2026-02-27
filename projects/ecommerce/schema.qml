version: "1.0"
connection: duckdb:///data/ecommerce.db

sources:
  orders:
    table: orders
    description: Individual customer orders with revenue and status

    dimensions:
      order_id:
        type: string
        column: order_id
        description: Unique order identifier

      order_date:
        type: date
        column: order_date
        hint: Use for time-based trending and seasonality analysis
        description: Date the order was placed

      region:
        type: string
        column: region
        hint: Use to compare geographic performance — look for underperforming regions
        description: Geographic region of the customer

      customer_segment:
        type: string
        column: customer_segment
        hint: Segments are Consumer, Corporate, Home Office — compare spending patterns
        description: Customer segment classification

      status:
        type: string
        column: status
        hint: Values are completed, returned, cancelled — use to analyze return/cancel rates
        description: Order fulfillment status

    measures:
      total_revenue:
        type: sum
        column: revenue
        hint: Primary revenue metric — use for overall business health
        context: "Monthly revenue benchmark is ~$50K. Below $40K signals a problem."
        description: Total revenue from orders

      order_count:
        type: count
        hint: Volume metric — high revenue with low order count means high AOV
        context: "Healthy monthly order volume is 200+. Below 150 needs investigation."
        description: Number of orders

      avg_order_value:
        type: avg
        column: revenue
        hint: Average revenue per order — compare across segments and regions
        context: "Benchmark AOV is $250. Consumer segment is typically lower (~$180), Corporate higher (~$350)."
        description: Average revenue per order

      return_rate:
        type: ratio
        numerator: is_returned
        denominator: order_count_raw
        hint: Percentage of orders that were returned — high return rate erodes margins
        context: "Healthy return rate is below 8%. Above 12% is a red flag. Check by category."
        description: Ratio of returned orders to total orders

  products:
    table: products
    description: Product catalog with categories and pricing

    dimensions:
      product_id:
        type: string
        column: product_id
        description: Unique product identifier

      product_name:
        type: string
        column: product_name
        hint: Use for product-level drill-downs
        description: Name of the product

      category:
        type: string
        column: category
        hint: Categories are Electronics, Clothing, Home, Office Supplies — compare category performance
        description: Product category

      sub_category:
        type: string
        column: sub_category
        hint: Drill into sub-categories when a category underperforms
        description: Product sub-category

  customers:
    table: customers
    description: Customer directory with segments and regions

    dimensions:
      customer_id:
        type: string
        column: customer_id
        description: Unique customer identifier

      customer_name:
        type: string
        column: customer_name
        description: Customer full name

datasets:
  sales_overview:
    label: Sales Overview
    description: Comprehensive sales analysis joining orders with products and customers. Use for revenue trends, segment analysis, category performance, and return rate investigation.
    source: orders
    joins:
      products:
        on: "orders.product_id = products.product_id"
        type: left
        relationship: many_to_one
      customers:
        on: "orders.customer_id = customers.customer_id"
        type: left
        relationship: many_to_one

  product_performance:
    label: Product Performance
    description: Product-level analysis — which products and categories drive revenue and which have high return rates.
    source: orders
    joins:
      products:
        on: "orders.product_id = products.product_id"
        type: left
        relationship: many_to_one

projects:
  ecommerce:
    label: E-Commerce Analytics
    description: Sales and product analytics for an online retail store
    datasets:
      - sales_overview
      - product_performance
    system_context: |
      You are an expert e-commerce analyst investigating sales data for an online retail store.

      When analyzing data:
      - Always start by understanding the overall picture before drilling down
      - Compare metrics against the benchmarks provided in measure context
      - Look for anomalies — segments or categories that deviate from the norm
      - When you find something unusual, drill deeper to find the root cause
      - Provide actionable recommendations, not just observations

      Key business context:
      - The store sells across Electronics, Clothing, Home, and Office Supplies
      - Customer segments are Consumer (largest), Corporate, and Home Office
      - Regions are West, East, Central, South
      - Return rates above 12% need immediate attention
      - Revenue trends should be checked for seasonality
