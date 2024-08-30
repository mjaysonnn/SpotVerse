
import warnings

import matplotlib.pyplot as plt


# Suppress warnings judiciously
warnings.filterwarnings("ignore", category=DeprecationWarning)

spot_instances = {'us-west': 150, 'us-east': 200, 'eu-central': 100, 'asia-southeast': 50}


def plot_pie_chart(data):
    """Plot a pie chart of the spot instances distribution across regions."""
    fig, ax = plt.subplots()
    ax.pie(data.values(), labels=data.keys(), autopct='%1.1f%%', startangle=90)
    ax.axis('equal')  # Equal aspect ratio ensures the pie is drawn as a circle.

    plt.title('Distribution of Spot Instances Across Regions')
    plt.show()


def plot_bar_chart(data):
    """Plot a bar chart of the spot instances distribution across regions."""
    fig, ax = plt.subplots()
    ax.bar(data.keys(), data.values(), color=['blue', 'green', 'red', 'purple'])

    # Adding labels and title
    plt.ylabel('Number of Instances')
    plt.xlabel('Region')
    plt.title('Distribution of Spot Instances Across Regions')

    # Adding value annotations on each bar
    for region, count in data.items():
        ax.text(region, count + 5, str(count), ha='center', va='bottom')

    # Display the plot
    plt.show()


def main():
    plot_pie_chart(spot_instances)
    plot_bar_chart(spot_instances)


if __name__ == "__main__":
    main()
