import streamlit as st
import requests
import pandas as pd
import time
import logging

# Configure logging
logging.basicConfig(level=logging.DEBUG, 
                    format='%(asctime)s - %(levelname)s - %(message)s',
                    handlers=[
                        logging.StreamHandler(),
                        logging.FileHandler('shopify_price_sync_debug.log')
                    ])

def fetch_eorder_prices(api_url):
    """
    Fetch prices and SKUs from the eOrder API with error handling
    """
    try:
        logging.info(f"Fetching prices from eOrder API: {api_url}")
        response = requests.get(api_url)
        logging.debug(f"eOrder API Response Status: {response.status_code}")
        
        if response.status_code == 200:
            prices = response.json()
            logging.info(f"Fetched {len(prices)} prices from eOrder")
            return prices
        else:
            logging.error(f"Failed to fetch data from eOrder. HTTP Status Code: {response.status_code}")
            logging.error(f"Response Content: {response.text}")
            st.error(f"Failed to fetch data from eOrder. HTTP Status Code: {response.status_code}")
            return None
    except Exception as e:
        logging.exception(f"An error occurred while fetching eOrder prices: {e}")
        st.error(f"An error occurred while fetching eOrder prices: {e}")
        return None

def get_shopify_products(shop_url, access_token):
    """
    Fetch Shopify products using Admin API with pagination
    """
    all_products = []
    next_page_url = f"https://{shop_url}/admin/api/2023-04/products.json?limit=250"
    
    while next_page_url:
        try:
            logging.info(f"Fetching Shopify products from: {next_page_url}")
            response = requests.get(
                next_page_url,
                headers={
                    'X-Shopify-Access-Token': access_token,
                    'Content-Type': 'application/json'
                }
            )
            
            logging.debug(f"Shopify Products Response Status: {response.status_code}")
            
            if response.status_code != 200:
                logging.error(f"Failed to fetch products. Status: {response.status_code}")
                logging.error(f"Response Content: {response.text}")
                st.error(f"Failed to fetch products. Status: {response.status_code}")
                break
            
            data = response.json()
            all_products.extend(data['products'])
            
            # Check for pagination link in headers
            next_page_url = None
            if 'Link' in response.headers:
                links = response.headers['Link'].split(', ')
                for link in links:
                    if 'rel="next"' in link:
                        next_page_url = link.split(';')[0].strip('<>')
        
        except Exception as e:
            logging.exception(f"Error fetching Shopify products: {e}")
            st.error(f"Error fetching Shopify products: {e}")
            break
    
    logging.info(f"Total Shopify products fetched: {len(all_products)}")
    return all_products

def compare_prices(eorder_prices, shopify_products):
    """
    Compare prices between eOrder and Shopify, track potential updates
    """
    price_updates = []
    
    # Create a dictionary of eOrder prices for quick lookup
    eorder_price_map = {item['sku']: float(item['price']) for item in eorder_prices}
    logging.debug(f"eOrder Price Map: {eorder_price_map}")
    
    for product in shopify_products:
        for variant in product['variants']:
            sku = variant.get('sku', '')
            
            if sku in eorder_price_map:
                current_price = float(variant['price'])
                new_price = eorder_price_map[sku]
                
                if abs(current_price - new_price) > 0.01:  # Allow small floating-point differences
                    update_info = {
                        'product_id': product['id'],
                        'variant_id': variant['id'],
                        'product_title': product['title'],
                        'variant_title': variant['title'],
                        'current_price': current_price,
                        'new_price': new_price,
                        'sku': sku
                    }
                    price_updates.append(update_info)
                    logging.info(f"Price update needed: {update_info}")
    
    logging.info(f"Total price updates to be processed: {len(price_updates)}")
    return price_updates

def update_shopify_price(shop_url, access_token, variant_id, new_price):
    """
    Update the price of a Shopify product variant with extensive logging
    """
    update_url = f"https://{shop_url}/admin/api/2023-04/variants/{variant_id}.json"
    
    headers = {
        'X-Shopify-Access-Token': access_token,
        'Content-Type': 'application/json'
    }
    
    payload = {
        "variant": {
            "id": variant_id,  # Include variant ID
            "price": f"{new_price:.2f}"
        }
    }
    
    try:
        # Detailed logging of request details
        logging.info(f"Attempting to update variant {variant_id}")
        logging.debug(f"Update URL: {update_url}")
        logging.debug(f"Payload: {payload}")
        
        response = requests.put(update_url, headers=headers, json=payload)
        
        logging.info(f"Response Status Code: {response.status_code}")
        
        # Log full response details for debugging
        logging.debug(f"Response Headers: {response.headers}")
        
        try:
            response_json = response.json()
            logging.debug(f"Response JSON: {response_json}")
        except ValueError:
            logging.debug(f"Response Text: {response.text}")
        
        if response.status_code == 200:
            logging.info(f"Successfully updated variant {variant_id} to price {new_price}")
            return True, response.json()
        else:
            error_msg = f"HTTP {response.status_code}: {response.text}"
            logging.error(f"Failed to update variant {variant_id}: {error_msg}")
            return False, error_msg
    
    except Exception as e:
        error_msg = str(e)
        logging.exception(f"Exception updating variant {variant_id}: {error_msg}")
        return False, error_msg

def main():
    # Rest of the code remains the same as in the previous version
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
    st.write("Fetching prices from eOrder API...")
    eorder_prices = fetch_eorder_prices(eorder_api_url)
    
    if not eorder_prices:
        st.error("Could not fetch prices from eOrder API.")
        return
    
    # Fetch Shopify Products
    st.write("Fetching Shopify products...")
    shopify_products = get_shopify_products(shopify_shop, shopify_access_token)
    
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
        st.write(f"Total products to be updated: {len(price_updates)}")
        
        # Confirm and Push Updates
        if st.button("Push Price Updates to Shopify"):
            st.write("Starting price update process...")
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
                progress_bar.progress((index + 1) / len(price_updates))
                status_text.text(f"Processed {index + 1} of {len(price_updates)} variants.")
                time.sleep(0.1)  # Small delay to make updates visible
            
            # Display Update Results
            results_df = pd.DataFrame(update_results)
            st.write("## Update Results")
            st.dataframe(results_df)
            success_count = results_df[results_df['Status'] == 'Success'].shape[0]
            failure_count = results_df[results_df['Status'].str.startswith('Failed')].shape[0]
            st.success(f"Price updates completed. Success: {success_count}, Failed: {failure_count}")
    else:
        st.success("No price updates needed!")

if __name__ == "__main__":
    main()
