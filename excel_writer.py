import pandas as pd


def save_to_excel(patents, output_file):
    df = pd.DataFrame(patents)
    df.to_excel(output_file, index=False)