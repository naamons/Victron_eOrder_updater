import streamlit as st
import requests
import shopify
import pandas as pd

def fetch_eorder_prices(api_url):
    """
    Fetch prices and SKUs from the eOrder API with error handling
    """
    try:
        response = requests.get(api_url)
        if response.status_code == 200:
            return response.json()
        else:
            st.error(f"Failed to fetch data. HTTP Status Code: {response.status_code}")
            return None
    except Exception as e:
        st.error(f"An error occurred while fetching eOrder prices: {e}")
        return None

def get_shopify_products(page_size=250):
    """
    Fetch Shopify products with pagination
    """
    all_products = []
    page = 1
    
    while True:
        try:
            products = shopify.Product.find(limit=page_size, page=page)
            
            if not products:
                break
            
            # Convert products to dictionary for easier processing
            product_dicts = [
                {
                    'id': product.id,
                    'variants': [
                        {
                            'id': variant.id, 
                            'sku': variant.sku, 
                            'price': variant.price
                        } for variant in product.variants
                    ]
                } for product in products
            ]
            
            all_products.extend(product_dicts)
            page += 1
        
        except Exception as e:
            st.error(f"Error fetching Shopify products: {e}")
            break
    
    return all_products

def compare_prices(eorder_prices, shopify_products):
    """
    Compare prices between eOrder and Shopify, track potential updates
    """
    price_updates = []
    
    # Create a dictionary of eOrder prices for quick lookup
    eorder_price_map = {item['sku']: item['price'] for item in eorder_prices}
    
    for product in shopify_products:
        for variant in product['variants']:
            sku = variant.get('sku', '')
            
            if sku in eorder_price_map:
                current_price = float(variant['price'])
                new_price = float(eorder_price_map[sku])
                
                if abs(current_price - new_price) > 0.01:  # Allow small floating-point differences
                    price_updates.append({
                        'product_id': product['id'],
                        'variant_id': variant['id'],
                        'current_price': current_price,
                        'new_price': new_price,
                        'sku': sku
                    })
    
    return price_updates

def main():
    st.title("Victron Energy Price Synchronization")
    st.write("Compare and synchronize prices between eOrder API and Shopify Storefront")

    # Fetch credentials from Streamlit secrets
    try:
        shopify_shop = st.secrets["SHOPIFY_SHOP"]
        shopify_access_token = st.secrets["SHOPIFY_ACCESS_TOKEN"]
        eorder_api_url = st.secrets["EORDER_API_URL"]
    except KeyError as e:
        st.error(f"Missing secret: {e}. Please configure Streamlit secrets.")
        return

    # Initialize Shopify Session
    try:
        session = shopify.Session(shopify_shop, '2023-04', shopify_access_token)
        shopify.ShopifyResource.activate_session(session)
    except Exception as e:
        st.error(f"Failed to initialize Shopify session: {e}")
        return

    # Fetch eOrder Prices
    st.write("Fetching prices from eOrder API...")
    eorder_prices = fetch_eorder_prices(eorder_api_url)
    
    if not eorder_prices:
        st.error("Could not fetch prices from eOrder API.")
        return

    # Fetch Shopify Products
    st.write("Fetching Shopify products...")
    shopify_products = get_shopify_products()
    
    if not shopify_products:
        st.error("Could not fetch Shopify products.")
        return

    # Compare Prices
    price_updates = compare_prices(eorder_prices, shopify_products)

    # Display Potential Price Updates
    st.header("Potential Price Updates")
    if price_updates:
        update_df = pd.DataFrame(price_updates)
        st.dataframe(update_df)
        st.write(f"Total products that would be updated: {len(price_updates)}")
    else:
        st.success("No price updates needed!")

    # Dry Run Update Button (for demonstration)
    if st.button("Simulate Price Update"):
        for update in price_updates:
            st.write(f"Would update SKU {update['sku']}: "
                     f"${update['current_price']} → ${update['new_price']}")

    # Close Shopify session
    shopify.ShopifyResource.clear_session()

if __name__ == "__main__":
    main()
