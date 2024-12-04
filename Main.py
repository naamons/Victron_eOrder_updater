import streamlit as st
import requests
import pandas as pd
import time
import json

def update_shopify_price(shop_url, access_token, variant_id, new_price):
    """
    Update the price of a Shopify product variant with debug printing.
    
    Args:
        shop_url (str): Your Shopify store URL (e.g., 'your-store.myshopify.com').
        access_token (str): Shopify API access token with 'write_products' scope.
        variant_id (int): The ID of the Shopify product variant to update.
        new_price (float): The new price to set for the variant.
    
    Returns:
        tuple: (success (bool), response or error message)
    """
    update_url = f"https://{shop_url}/admin/api/2023-04/variants/{variant_id}.json"
    
    headers = {
        'X-Shopify-Access-Token': access_token,
        'Content-Type': 'application/json'
    }
    
    payload = {
        "variant": {
            "id": variant_id,  # Include the variant ID here
            "price": f"{new_price:.2f}"
        }
    }
    
    # Debug Information
    print("DEBUG: Shopify Price Update Details")
    print(f"URL: {update_url}")
    print(f"Variant ID: {variant_id}")
    print(f"New Price: {new_price}")
    print("Payload:")
    print(json.dumps(payload, indent=2))
    
    try:
        response = requests.put(update_url, headers=headers, json=payload)
        
        # Debugging the API response
        print("\nDEBUG: API Response")
        print(f"Status Code: {response.status_code}")
        print("Response Headers:")
        print(json.dumps(dict(response.headers), indent=2))
        
        try:
            response_json = response.json()
            print("\nResponse JSON:")
            print(json.dumps(response_json, indent=2))
        except ValueError:
            print("\nResponse Text:")
            print(response.text)
        
        if response.status_code == 200:
            return True, response_json
        else:
            error_msg = f"HTTP {response.status_code}: {response.text}"
            print(f"\nDEBUG: Error - {error_msg}")
            return False, error_msg
    
    except Exception as e:
        error_msg = str(e)
        print(f"\nDEBUG: Exception - {error_msg}")
        return False, error_msg

def fetch_eorder_prices(api_url):
    """
    Fetch prices from the eOrder API.
    
    Args:
        api_url (str): The URL of the eOrder API endpoint.
    
    Returns:
        list or None: List of price data if successful, else None.
    """
    try:
        response = requests.get(api_url)
        if response.status_code == 200:
            return response.json()
        else:
            st.error(f"Failed to fetch data from eOrder. HTTP Status Code: {response.status_code}")
            return None
    except Exception as e:
        st.error(f"An error occurred while fetching eOrder prices: {e}")
        return None

def get_shopify_products(shop_url, access_token):
    """
    Retrieve all products from the Shopify store.
    
    Args:
        shop_url (str): Your Shopify store URL.
        access_token (str): Shopify API access token.
    
    Returns:
        list: List of all Shopify products.
    """
    all_products = []
    next_page_url = f"https://{shop_url}/admin/api/2023-04/products.json?limit=250"
    
    while next_page_url:
        try:
            response = requests.get(
                next_page_url,
                headers={
                    'X-Shopify-Access-Token': access_token,
                    'Content-Type': 'application/json'
                }
            )
            
            if response.status_code != 200:
                st.error(f"Failed to fetch products. Status: {response.status_code}")
                break
            
            data = response.json()
            all_products.extend(data.get('products', []))
            
            # Check for pagination link in headers
            next_page_url = None
            if 'Link' in response.headers:
                links = response.headers['Link'].split(', ')
                for link in links:
                    if 'rel="next"' in link:
                        next_page_url = link.split(';')[0].strip('<>')
                        break  # Only one next page link is expected
            
        except Exception as e:
            st.error(f"Error fetching Shopify products: {e}")
            break
    
    return all_products

def compare_prices(eorder_prices, shopify_products):
    """
    Compare prices between eOrder and Shopify products to identify discrepancies.
    
    Args:
        eorder_prices (list): List of price data from eOrder.
        shopify_products (list): List of Shopify products.
    
    Returns:
        list: List of products that require price updates.
    """
    price_updates = []
    
    # Create a dictionary of eOrder prices for quick lookup
    eorder_price_map = {item['sku']: float(item['price']) for item in eorder_prices}
    
    for product in shopify_products:
        for variant in product.get('variants', []):
            sku = variant.get('sku', '').strip()
            
            if sku in eorder_price_map:
                try:
                    current_price = float(variant.get('price', 0))
                    new_price = eorder_price_map[sku]
                    
                    if abs(current_price - new_price) > 0.01:  # Allow small floating-point differences
                        price_updates.append({
                            'product_id': product['id'],
                            'variant_id': variant['id'],
                            'product_title': product.get('title', 'N/A'),
                            'variant_title': variant.get('title', 'N/A'),
                            'current_price': current_price,
                            'new_price': new_price,
                            'sku': sku
                        })
                except ValueError:
                    st.warning(f"Invalid price format for SKU: {sku}")
    
    return price_updates

def main():
    st.set_page_config(page_title="Victron Energy Price Synchronization", layout="wide")
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
    
    # Validate `shopify_shop` format
    if shopify_shop.startswith("https://") or shopify_shop.startswith("http://"):
        st.error("SHOPIFY_SHOP should not include the protocol (e.g., use 'your-store.myshopify.com')")
        return
    
    # Fetch eOrder Prices
    st.header("1. Fetching Prices from eOrder API")
    with st.spinner("Fetching prices from eOrder API..."):
        eorder_prices = fetch_eorder_prices(eorder_api_url)
    
    if not eorder_prices:
        st.error("Could not fetch prices from eOrder API.")
        return
    
    st.success("Successfully fetched prices from eOrder API.")
    
    # Fetch Shopify Products
    st.header("2. Fetching Shopify Products")
    with st.spinner("Fetching Shopify products..."):
        shopify_products = get_shopify_products(shopify_shop, shopify_access_token)
    
    if not shopify_products:
        st.error("Could not fetch Shopify products.")
        return
    
    st.success(f"Successfully fetched {len(shopify_products)} products from Shopify.")
    
    # Compare Prices
    st.header("3. Comparing Prices")
    price_updates = compare_prices(eorder_prices, shopify_products)
    
    # Display Potential Price Updates
    st.header("4. Potential Price Updates")
    if price_updates:
        update_df = pd.DataFrame(price_updates)
        st.dataframe(update_df[['sku', 'product_title', 'variant_title', 'current_price', 'new_price']])
        st.write(f"Total products to be updated: {len(price_updates)}")
        
        # Confirm and Push Updates
        if st.button("Push Price Updates to Shopify"):
            st.info("Starting price update process...")
            update_results = []
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            for index, update in enumerate(price_updates):
                success, result = update_shopify_price(
                    shop_url=shopify_shop,
                    access_token=shopify_access_token,
                    variant_id=update['variant_id'],
                    new_price=update['new_price']
                )
                if success:
                    update_results.append({
                        'SKU': update['sku'],
                        'Product': update['product_title'],
                        'Variant': update['variant_title'],
                        'Old Price': update['current_price'],
                        'New Price': update['new_price'],
                        'Status': 'Success'
                    })
                else:
                    update_results.append({
                        'SKU': update['sku'],
                        'Product': update['product_title'],
                        'Variant': update['variant_title'],
                        'Old Price': update['current_price'],
                        'New Price': update['new_price'],
                        'Status': f'Failed: {result}'
                    })
                
                # Update progress
                progress_percentage = (index + 1) / len(price_updates)
                progress_bar.progress(progress_percentage)
                status_text.text(f"Processed {index + 1} of {len(price_updates)} variants.")
                time.sleep(0.05)  # Small delay to make updates visible
            
            # Display Update Results
            results_df = pd.DataFrame(update_results)
            st.header("5. Update Results")
            st.dataframe(results_df)
            success_count = results_df[results_df['Status'] == 'Success'].shape[0]
            failure_count = results_df[results_df['Status'].str.startswith('Failed')].shape[0]
            st.success(f"Price updates completed. Success: {success_count}, Failed: {failure_count}")
    else:
        st.success("No price updates needed!")

if __name__ == "__main__":
    main()
