import streamlit as st
import requests

# Define the Streamlit app
def main():
    # Set up the title and description
    st.title("Victron Energy SKU Prices Viewer")
    st.write("This app fetches and displays product SKUs and their prices from the Victron Energy API.")

    # Define the API endpoint
    api_url = "https://eorder.victronenergy.com/api/v1/pricelist/map/us/"

    # Fetch data from the API
    try:
        st.write("Fetching data from the API...")
        response = requests.get(api_url)

        # Check if the request was successful
        if response.status_code == 200:
            data = response.json()
            st.success("Data fetched successfully!")
            
            # Create a table to display the data
            if data:
                st.write("Here is the list of SKUs and prices:")
                for product in data:
                    sku = product.get("sku", "N/A")
                    price = product.get("price", "N/A")
                    st.write(f"**SKU:** {sku} | **Price:** {price}")
            else:
                st.warning("No data found!")
        else:
            st.error(f"Failed to fetch data. HTTP Status Code: {response.status_code}")
    except Exception as e:
        st.error(f"An error occurred: {e}")

# Run the Streamlit app
if __name__ == "__main__":
    main()
