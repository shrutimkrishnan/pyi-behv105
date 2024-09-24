import streamlit as st
import pandas as pd
import plotly.graph_objects as go

# Set page layout to wide
st.set_page_config(layout="wide")

# Read the CSV file from the public S3 URL
data = pd.read_csv("https://behaviorally-testing.s3.amazonaws.com/sankey_relevant_session_v2.csv")

st.title("Behaviorally Sankey beh_v105")
st.write("Sankey Diagram of Participant Journeys")

# App selection dropdown
app_names = {
    'com.ss.android.ugc.trill': 'TikTok',
    'com.shopee.id': 'Shopee'
}
selected_app = st.selectbox("Select App", options=list(app_names.keys()), format_func=lambda x: app_names[x])

# Filter the data after app selection
if selected_app:
    app_data = data[data['apppackagename'] == selected_app]
    print(app_data)

    app_data['participantId'] = app_data['participantId'].astype('str')

    # Order the participant_ids numerically and add an "All" option
    participant_ids = sorted(app_data['participantId'].unique())
    participant_ids = ['All'] + participant_ids  # Add "All" option at the beginning

    # Filter dropdown for participantId
    selected_participant = st.selectbox("Select Participant", participant_ids)

    # Third filter for journey type
    journey_types = ["Purchase", "Non-Purchase"]
    selected_journey_type = st.selectbox("Select Journey Type", journey_types, index=0)  # "Purchase" is default

    # Function to process the journeys until purchases
    def journeys_until_first_purchase(pages):
        if not pages:
            return []

        journeys = []
        current_journey = [pages[0]]

        for i in range(1, len(pages)):
            if pages[i] == 'Purchase':
                current_journey.append(pages[i])
                journeys.append(current_journey)
                break  # Stop after the first purchase
            elif pages[i] != pages[i - 1]:  # Compare with the previous element
                current_journey.append(pages[i])

        if 'Purchase' not in current_journey:
            journeys.append(current_journey)

        return journeys

    def get_sankey_format_data(df):
        # Exploding the 'url_path' into separate rows
        df_exploded = df.explode('pagetype')

        # Adding Step column based on the order within each session
        df_exploded['Step'] = df_exploded.groupby(['participantId', 'session']).cumcount()

        # Pivoting the DataFrame to get Step columns
        df_pivoted = df_exploded.pivot(index=['participantId', 'session'], columns='Step', values='pagetype')

        # Renaming the columns to match the desired Step format
        df_pivoted.columns = [f'Step{col}' for col in df_pivoted.columns]

        # Resetting index to flatten the DataFrame
        df_pivoted.reset_index(inplace=True)

        # Reordering the columns to match the desired format
        df_final = df_pivoted[['participantId', 'session'] + [f'Step{i}' for i in range(df_pivoted.shape[1] - 2)]]

        return df_final

    def get_first_and_last_five_journeys(list_items):
        if len(list_items) > 10:
            return list_items[:5] + list_items[-5:]
        return list_items

    def get_journeys_until_first_purchase(df, app_package_name, participant_id):
        if participant_id == 'All':
            app_df = df[df['apppackagename'] == app_package_name]
        else:
            app_df = df[(df['apppackagename'] == app_package_name) & (df['participantId'] == participant_id)]
        
        app_df['pagetype'] = app_df['pagetype'].str.split('|')
        app_df = app_df.explode('pagetype', ignore_index=True)
        app_df = app_df[app_df['pagetype'] != 'Viewedrecommendedproduct']
        app_df['pagetype'] = app_df['pagetype'].replace('Cart', 'Cart Journey')
        app_df['eventtime'] = pd.to_datetime(app_df['eventtime'])
        app_df.sort_values(by=['participantId', 'eventtime', 'session'], inplace=True)
        aggregated_data = app_df.groupby(['participantId', 'session']).agg({'pagetype': list}).reset_index()
        aggregated_data['pagetype'] = aggregated_data['pagetype'].apply(journeys_until_first_purchase)
        aggregated_data = aggregated_data.explode('pagetype')
        aggregated_data = aggregated_data[~aggregated_data['pagetype'].isnull()]
        aggregated_data['pagetype'] = aggregated_data['pagetype'].apply(lambda x: x + ['Non-Purchase'] if x[-1] != 'Purchase' else x)
        aggregated_data['pagetype_length'] = aggregated_data['pagetype'].apply(len)
        aggregated_data = aggregated_data[aggregated_data['pagetype_length'] > 1]
        aggregated_data['pagetype'] = aggregated_data['pagetype'].apply(get_first_and_last_five_journeys)
        aggregated_data['journey_type'] = aggregated_data['pagetype'].apply(lambda x: 'Non Purchase Journeys' if x[-1] != 'Purchase' else 'Purchase Journeys')
        aggregated_data['pagetype_length'] = aggregated_data['pagetype'].apply(len)

        # Filter data based on selected journey type
        if selected_journey_type == "Purchase":
            filtered_df = aggregated_data[aggregated_data['journey_type'] == 'Purchase Journeys']
        else:
            filtered_df = aggregated_data[aggregated_data['journey_type'] == 'Non Purchase Journeys']

        return get_sankey_format_data(filtered_df)

    # Filter the data based on the selected participant and journey type
    purchase_paths_df = get_journeys_until_first_purchase(data, selected_app, selected_participant)

    event_colors = {
        "Home": "#d02f80",
        "Search": "#d98c26",
        "Review": "#abd629",
        "Category": "#68d22d",
        "Product": "#2bd4bd",
        "Cart Journey": "#229cdd",
        "Checkout":"#229ddd",
        "Purchase": "#964db2",
        "Videolive": "#9a7965",
        "Videononlive": "#9a7345",
        "Voucher": "#6e918b",
        "History": "#edda12",
        "Brandshop": "#64739b",
        "Me":"#63d6d6",
        "Non-Purchase": "#63d8d6",
        "Shopeemall":"#23d8d6",
        "Allproductsandservices":"#62d8d6",
    }

    # Initialize lists for sources, targets, values, and colors
    source = []
    target = []
    value = []
    link_colors = []

    # Create dictionaries to store node labels and indices
    node_labels = []
    node_indices = {}
    node_colors = []

    # Helper function to get the index of a node label
    def get_node_index(label):
        if label not in node_indices:
            node_indices[label] = len(node_labels)
            node_labels.append(label)
            node_colors.append(event_colors[label.split("_")[1]] if "_" in label else event_colors.get(label, "grey"))
        return node_indices[label]

    # Iterate over each row to build the source-target pairs
    for index, row in purchase_paths_df.iterrows():
        steps = row.dropna().tolist()[2:]  # Exclude PID and SID
        for i in range(len(steps) - 1):
            current_step = steps[i]
            next_step = steps[i + 1]

            # Ensure all non-purchase paths end at a single node "Non-Purchase"
            if next_step == 'Non-Purchase':
                next_step_label = 'Non-Purchase'
            elif next_step == 'Purchase':
                next_step_label = 'Purchase'
            else:
                next_step_label = f"Step{i + 1}_{next_step}"

            source_index = get_node_index(f"Step{i}_{current_step}")
            target_index = get_node_index(next_step_label)

            source.append(source_index)
            target.append(target_index)
            value.append(1)  # Each transition has a value of 1
            link_colors.append("lightgrey")  # Transition color

    # Create the Sankey diagram
    fig = go.Figure(go.Sankey(
        node=dict(
            pad=20,  # Increased padding for clearer separation
            thickness=20,
            line=dict(color="black", width=0.5),
            label=[label.split("_")[1] if "_" in label else label for label in node_labels],
            color=node_colors
        ),
        link=dict(
            source=source,
            target=target,
            value=value,
            color=link_colors
        )
    ))

    # Update layout to control font settings globally and set the width of the figure
    fig.update_layout(
        title_text="E-commerce Purchase Journeys (First 5 steps, Last 5 steps only)",
        font=dict(
            size=14,  # Larger font size
            color="black",  # Set font color to black for better contrast
            family="Arial"  # Simpler, more readable font
        ),
        font_size=10,  # Additional font size control
        width=1400,  # Set width for wide-screen display
        height=800  # Optional: Set height if needed
    )

    # Display the Sankey diagram in Streamlit with full width
    st.plotly_chart(fig, use_container_width=True)