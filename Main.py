import streamlit as st
import requests
import pandas as pd
import time
import base64
from io import StringIO

def fetch_eorder_prices(api_url):
    """
    Fetch prices and SKUs from the eOrder API with error handling
    """
    try:
        response = requests.get(api_url)
        if response.status_code == 200:
            return response.json()
        else:
            st.error(f"Failed to fetch data from eOrder. HTTP Status Code: {response.status_code}")
            try:
                st.json(response.json())  # Display error details
            except:
                st.write(response.text)
            return None
    except Exception as e:
        st.error(f"An error occurred while fetching eOrder prices: {e}")
        return None

def get_shopify_products(shop_url, access_token, api_version="2024-01"):
    """
    Fetch Shopify products using Admin API with pagination
    """
    all_products = []
    next_page_url = f"https://{shop_url}/admin/api/{api_version}/products.json?limit=250"
    
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
                try:
                    st.json(response.json())  # Display error details
                except:
                    st.write(response.text)
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
            st.error(f"Error fetching Shopify products: {e}")
            break
    
    return all_products

def compare_prices(eorder_prices, shopify_products):
    """
    Compare prices between eOrder and Shopify, track potential updates
    """
    price_updates = []
    
    # Create a dictionary of eOrder prices for quick lookup
    eorder_price_map = {item['sku']: float(item['price']) for item in eorder_prices}
    
    for product in shopify_products:
        for variant in product['variants']:
            sku = variant.get('sku', '')
            
            if sku in eorder_price_map:
                current_price = float(variant['price'])
                new_price = eorder_price_map[sku]
                option1 = variant.get('option1', '')
                option2 = variant.get('option2', '')
                option3 = variant.get('option3', '')
                
                if abs(current_price - new_price) > 0.01:  # Allow small floating-point differences
                    price_updates.append({
                        'product_id': product['id'],
                        'variant_id': variant['id'],
                        'product_title': product['title'],
                        'variant_title': variant['title'],
                        'current_price': current_price,
                        'new_price': new_price,
                        'sku': sku,
                        'option1': option1,
                        'option2': option2,
                        'option3': option3
                    })
    
    return price_updates

def update_shopify_price(shop_url, access_token, variant_id, new_price, option1, option2, option3, api_version="2024-01"):
    """
    Update the price and options of a Shopify product variant using the Admin API
    """
    update_url = f"https://{shop_url}/admin/api/{api_version}/variants/{variant_id}.json"
    payload = {
        "variant": {
            "id": variant_id,
            "price": f"{new_price:.2f}",
            "option1": option1,
            "option2": option2,
            "option3": option3
        }
    }

    headers = {
        'X-Shopify-Access-Token': access_token,
        'Content-Type': 'application/json'
    }

    try:
        response = requests.put(
            update_url,
            headers=headers,
            json=payload
        )
        
        if response.status_code == 200:
            st.success(f"Successfully updated Variant ID: {variant_id}")
            return True, response.json()
        else:
            # Log the full response for debugging
            st.error(f"Failed to update Variant ID {variant_id}. Status: {response.status_code}")
            try:
                st.json(response.json())  # Display the error message
            except:
                st.write(response.text)
            return False, response.json()
    except Exception as e:
        st.error(f"Exception occurred while updating Variant ID {variant_id}: {e}")
        return False, str(e)

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
        st.write(f"Total products that would be updated: {len(price_updates)}")
    else:
        st.success("No price updates needed!")
        return  # Exit if no updates are necessary

    # Initialize error log
    error_log = []

    st.header("Push Updates to Shopify")
    st.write("Click the button below to push the above price updates to your Shopify store.")

    if st.button("Push Price Updates"):
        if not price_updates:
            st.info("There are no price updates to push.")
            return

        progress_bar = st.progress(0)
        status_text = st.empty()
        success_updates = []
        failed_updates = []

        total_updates = len(price_updates)
        for idx, update in enumerate(price_updates, start=1):
            status_text.text(f"Updating {idx}/{total_updates}: SKU {update['sku']}")

            success, response = update_shopify_price(
                shop_url=shopify_shop,
                access_token=shopify_access_token,
                variant_id=update['variant_id'],
                new_price=update['new_price'],
                option1=update['option1'],
                option2=update['option2'],
                option3=update['option3']
            )

            if success:
                success_updates.append(update)
            else:
                failed_updates.append({
                    'sku': update['sku'],
                    'variant_id': update['variant_id'],
                    'error': response
                })
                # Append to error log
                error_details = f"SKU: {update['sku']}, Variant ID: {update['variant_id']}, Error: {response}"
                error_log.append(error_details)

            progress_bar.progress(idx / total_updates)
            time.sleep(0.1)  # Optional: To simulate progress

        status_text.text("Price updates completed.")

        if success_updates:
            st.success(f"Successfully updated {len(success_updates)} variants.")
        if failed_updates:
            st.error(f"Failed to update {len(failed_updates)} variants.")
            failed_df = pd.DataFrame(failed_updates)
            st.dataframe(failed_df)

            # Prepare error.txt content
            error_content = "\n".join(error_log)
            st.download_button(
                label="Download Error Log",
                data=error_content,
                file_name='error.txt',
                mime='text/plain'
            )

        progress_bar.empty()
        status_text.empty()

    # Optional: Simulate Update for Dry Run
    st.header("Simulate Price Update")
    if st.button("Simulate Price Update"):
        for update in price_updates:
            st.write(f"Would update SKU {update['sku']}: "
                     f"${update['current_price']} → ${update['new_price']} "
                     f"for product: {update['product_title']} - {update['variant_title']}")


if __name__ == "__main__":
    main()
