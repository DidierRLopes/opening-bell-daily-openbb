import json
from pathlib import Path
import pandas as pd
import requests
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import plotly.graph_objects as go
# from plotly_templates import dark_template
import pandas as pd
from openbb import obb
from datetime import datetime
from fastapi.staticfiles import StaticFiles
import pytz
import base64


app = FastAPI()

app.mount("/static", StaticFiles(directory="static"), name="static")

origins = [
    "https://pro.openbb.co",
    "https://pro.openbb.dev",
    "https://excel.openbb.co"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

ROOT_PATH = Path(__file__).parent.resolve()

@app.get("/")
def read_root():
    return {"Info": "Full example for OpenBB Custom Backend"}


@app.get("/widgets.json")
def get_widgets():
    """Widgets configuration file for the OpenBB Custom Backend"""
    return JSONResponse(
        content=json.load((Path(__file__).parent.resolve() / "widgets.json").open())
    )


@app.get("/templates.json")
def get_templates():
    """Templates configuration file for the OpenBB Custom Backend"""
    return JSONResponse(
        content=json.load((Path(__file__).parent.resolve() / "templates.json").open())
    )


@app.get("/health")
def health_check():
    return {"status": "healthy"}


@app.get("/market_snapshot")
def get_market_snapshot():
    """Get current market snapshot of major indices and assets"""
    
    try:
        # Define the symbols we want to track
        symbols = {
            "^DJI": "DJIA",
            "^GSPC": "S&P 500",
            "^NDX": "NASDAQ",
            "^RUT": "Russell 2K",
            "GC=F": "Gold",
            "BTC-USD": "Bitcoin",
            "BZ=F": "Brent Crude",
            "^TNX": "10-year",
        }

        # Get current date and start of year date
        end_date = datetime.now()
        start_date = datetime(end_date.year, 1, 1)  # Start of the year for YTD

        image_path = Path(__file__).parent.resolve() / "obd.png"
        
        # Create a list to store our results
        results = []

        for symbol in list(symbols.keys()):
            try:
                # Fetch historical data using OpenBB
                df_historical = obb.equity.price.historical(
                    symbol=symbol,
                    provider="yfinance",
                    start_date=start_date.strftime("%Y-%m-%d")
                ).to_df()
                
                if df_historical.empty or len(df_historical) < 2:
                    print(f"Not enough data for {symbol}")
                    continue
                
                # Calculate 1-day percent change
                daily_change_pct = ((df_historical['close'].iloc[-1] - df_historical['close'].iloc[-2]) / 
                                    df_historical['close'].iloc[-2]) * 100
                
                # Calculate YTD change percent
                ytd_change_pct = ((df_historical['close'].iloc[-1] - df_historical['close'].iloc[0]) / 
                                df_historical['close'].iloc[0]) * 100
                
                # Get latest closing price
                latest_price = round(df_historical['close'].iloc[-1], 2)
                
                # Store as native Python types to avoid Series formatting issues
                results.append({
                    'Index': symbols.get(symbol, symbol),
                    '1-day change': float(daily_change_pct),
                    'YTD': float(ytd_change_pct),
                    'Value': float(latest_price)
                })
            except Exception as e:
                print(f"Error processing {symbol}: {str(e)}")
                continue

        if not results:
            return JSONResponse(
                content={"error": "No market data available"}, 
                status_code=500
            )

        # Create dataframe from results
        df = pd.DataFrame(results)

        # Format the values as strings with appropriate formatting
        daily_change_formatted = [f"{val:.2f}%" for val in df['1-day change']]
        ytd_formatted = [f"{val:.2f}%" for val in df['YTD']]
        value_formatted = [f"{val:,.2f}" for val in df['Value']]

        # Create the figure
        fig = go.Figure()

        fig.add_trace(go.Scatter(   
            x=[0], 
            y=[0],
            mode='markers',
            marker=dict(opacity=0, size=0),
            showlegend=False,
            hoverinfo='none'
        ))
        # Find max absolute values for scaling
        max_daily_abs = max(abs(df['1-day change'].max()), abs(df['1-day change'].min()))
        max_ytd_abs = max(abs(df['YTD'].max()), abs(df['YTD'].min()))

        # Scale factors - adjust these to control maximum bar width
        daily_scale = 0.08 / max_daily_abs  # Reduced from 0.1 to 0.08 for more spacing
        ytd_scale = 0.08 / max_ytd_abs      # Reduced from 0.1 to 0.08 for more spacing

        # Calculate row heights and positions
        num_rows = len(df)
        table_height = 0.9  # Table takes up 90% of the paper height
        header_height = 0.1  # Header takes up 10% of the paper height
        row_height = (table_height - header_height) / num_rows

        # Adjust column positions to add more spacing
        header_positions = [0, 0.35, 0.65, 1]  # Spread out column centers
        header_alignments = ['left', 'center', 'center', 'right']

        # Add header text annotations
        headers = ['', '1-day change', 'YTD', 'Value']

        for i, header in enumerate(headers):
            fig.add_annotation(
                x=header_positions[i],
                y=1.0 - (header_height/2),  # Center in header area
                text=f"<b>{header}</b>",
                showarrow=False,
                font=dict(size=18, color='black'),
                xref="paper",
                yref="paper",
                xanchor=header_alignments[i],
                yanchor="middle"
            )

        # Add horizontal bold border between headers and content
        fig.add_shape(
            type="line",
            x0=0,
            x1=1,
            y0=1.0 - header_height,
            y1=1.0 - header_height,
            line=dict(color="black", width=2),
            xref="paper",
            yref="paper"
        )

        # Add index column values
        for i, index_value in enumerate(df['Index']):
            y_center = 1.0 - header_height - (i * row_height) - (row_height / 2)
            fig.add_annotation(
                x=header_positions[0],  # Position in the Index column
                y=y_center,
                text=f"<b>{index_value}</b>",  # Added bold HTML tags
                showarrow=False,
                font=dict(size=16, color='black'),
                xref="paper",
                yref="paper",
                xanchor="left",
                yanchor="middle"
            )
            # Add alternating row background
            if i % 2 == 0:
                fig.add_shape(
                    type="rect",
                    x0=0,
                    x1=1,
                    y0=1.0 - header_height - ((i+1) * row_height),
                    y1=1.0 - header_height - (i * row_height),
                    fillcolor='#edf7f8',
                    line=dict(width=0),
                    xref="paper",
                    yref="paper"
                )

        # Find max absolute values for scaling
        max_daily_abs = max(abs(df['1-day change'].max()), abs(df['1-day change'].min()))
        max_ytd_abs = max(abs(df['YTD'].max()), abs(df['YTD'].min()))

        # Scale factors - adjusted for more spacing
        daily_scale = 0.08 / max_daily_abs  # Reduced from 0.1 to 0.08
        ytd_scale = 0.08 / max_ytd_abs      # Reduced from 0.1 to 0.08

        # Calculate row heights and positions
        num_rows = len(df)
        table_height = 0.9  # Table takes up 90% of the paper height
        header_height = 0.1  # Header takes up 10% of the paper height
        row_height = (table_height - header_height) / num_rows

        # Add vertical reference lines at the center of 1-day change and YTD columns
        # For 1-day change column
        fig.add_shape(
            type="line",
            x0=header_positions[1],  # Center of 1-day change column
            x1=header_positions[1],
            y0=1.0 - header_height,  # Start below the header
            y1=1.0 - header_height - (num_rows * row_height),  # End at the bottom of the table
            line=dict(color="black", width=1),
            xref="paper",
            yref="paper"
        )

        # For YTD column
        fig.add_shape(
            type="line",
            x0=header_positions[2],  # Center of YTD column
            x1=header_positions[2],
            y0=1.0 - header_height,  # Start below the header
            y1=1.0 - header_height - (num_rows * row_height),  # End at the bottom of the table
            line=dict(color="black", width=1),
            xref="paper",
            yref="paper"
        )
        
        # Create visual indicators for each row
        for i, row in df.iterrows():
            daily_change = row['1-day change']
            ytd_change = row['YTD']
            
            # Determine colors based on positive/negative values
            daily_color = "#0024b5" if daily_change >= 0 else "#c81c1d"
            ytd_color = "#0024b5" if ytd_change >= 0 else "#c81c1d"
            
            # Calculate y-positions to align with table rows
            y_center = 1.0 - header_height - (i * row_height) - (row_height / 2)
            bar_height = row_height * 0.4
            y_top_centered = y_center + (bar_height / 2)
            y_bottom_centered = y_center - (bar_height / 2)
            
            # Column positions
            daily_center = header_positions[1]
            ytd_center = header_positions[2]
            
            # For 1-day change:
            if daily_change >= 0:
                daily_x0 = daily_center
                daily_x1 = daily_center + (daily_change * daily_scale)
            else:
                daily_x0 = daily_center + (daily_change * daily_scale)
                daily_x1 = daily_center
            
            # Add 1-day change bar
            fig.add_shape(
                type="rect",
                x0=daily_x0,
                x1=daily_x1,
                y0=y_bottom_centered,
                y1=y_top_centered,
                fillcolor=daily_color,
                line=dict(width=0),
                xref="paper",
                yref="paper",
                opacity=0.7
            )
            
            # For YTD - handle all indices including Bitcoin
            if row['Index'] != "10-year":
                # For YTD:
                if ytd_change >= 0:
                    ytd_x0 = ytd_center
                    ytd_x1 = ytd_center + (ytd_change * ytd_scale)
                else:
                    ytd_x0 = ytd_center + (ytd_change * ytd_scale)
                    ytd_x1 = ytd_center
            
                # Add YTD bar
                fig.add_shape(
                    type="rect",
                    x0=ytd_x0,
                    x1=ytd_x1,
                    y0=y_bottom_centered,
                    y1=y_top_centered,
                    fillcolor=ytd_color,
                    line=dict(width=0),
                    xref="paper",
                    yref="paper",
                    opacity=0.7
                )
            
            # Add 1-day change text - improved positioning logic
            daily_text = daily_change_formatted[i]
            daily_bar_width = abs(daily_x1 - daily_x0)
            daily_text_width_estimate = len(daily_text) * 0.01
            
            # Determine text position and color
            if daily_bar_width > daily_text_width_estimate * 1.2:
                # Text fits inside bar
                daily_text_x = (daily_x0 + daily_x1) / 2
                daily_text_color = "white"
                daily_text_anchor = "center"
            else:
                # Text outside bar - position based on direction
                if daily_change >= 0:
                    daily_text_x = daily_x1 + 0.01
                    daily_text_anchor = "left"
                else:
                    daily_text_x = daily_x0 - 0.01
                    daily_text_anchor = "right"
                daily_text_color = "black"
            
            # Add 1-day change text annotation
            fig.add_annotation(
                x=daily_text_x,
                y=y_center,
                text=daily_text,
                showarrow=False,
                font=dict(color=daily_text_color, size=14),
                xref="paper",
                yref="paper",
                xanchor=daily_text_anchor,
                yanchor="middle"
            )
            
            # For YTD change text - handle all indices including Bitcoin
            if row['Index'] != "10-year":
                ytd_text = ytd_formatted[i]
                ytd_bar_width = abs(ytd_x1 - ytd_x0)
                ytd_text_width_estimate = len(ytd_text) * 0.01
                
                # Determine text position and color
                if ytd_bar_width > ytd_text_width_estimate * 1.2:
                    # Text fits inside bar
                    ytd_text_x = (ytd_x0 + ytd_x1) / 2
                    ytd_text_color = "white"
                    ytd_text_anchor = "center"
                else:
                    # Text outside bar - position based on direction
                    if ytd_change >= 0:
                        ytd_text_x = ytd_x1 + 0.01
                        ytd_text_anchor = "left"
                    else:
                        ytd_text_x = ytd_x0 - 0.01
                        ytd_text_anchor = "right"
                    ytd_text_color = "black"
                
                # Add YTD change text annotation
                fig.add_annotation(
                    x=ytd_text_x,
                    y=y_center,
                    text=ytd_text,
                    showarrow=False,
                    font=dict(color=ytd_text_color, size=14),
                    xref="paper",
                    yref="paper",
                    xanchor=ytd_text_anchor,
                    yanchor="middle"
                )
            
            # Add value text with special formatting - ensure Bitcoin is handled correctly
            value_text = ""
            if row['Index'] == "Gold":
                value_text = f"${row['Value']:,} per ounce"
            elif row['Index'] == "Bitcoin":
                value_text = f"${row['Value']:,}"  # Make sure Bitcoin is formatted correctly
            elif row['Index'] == "Brent Crude":
                value_text = f"${row['Value']:,} a barrel"
            elif row['Index'] == "10-year":
                value_text = f"{row['Value']}%"
            else:
                value_text = f"{row['Value']:,}" if row['Value'] >= 1000 else str(row['Value'])
            
            # Add value text annotation
            fig.add_annotation(
                x=1.0,
                y=y_center,
                text=value_text,
                showarrow=False,
                font=dict(color="black", size=14),
                xref="paper",
                yref="paper",
                xanchor="right",
                yanchor="middle"
            )
        # Update layout
        fig.update_layout(
            title="",
            margin=dict(l=20, r=20, t=10, b=30),  # Increased bottom margin from 20 to 40
            height=len(df) * 40,  # Added 20px more height for spacing
            width=900,  # Increased width from 800 to 900 for more spacing
            plot_bgcolor='#F4FEFF',
            paper_bgcolor='#F4FEFF',
            dragmode=False,  # Disable dragging
            xaxis=dict(
                showticklabels=False,
                showgrid=False,
                zeroline=False,
                showline=False
            ),
            yaxis=dict(
                showticklabels=False,
                showgrid=False,
                zeroline=False,
                showline=False
            )
        )
        
        # Add the text annotation on the left
        fig.add_annotation(
            x=0,
            y=-0.01,
            text=f"<i><span style='font-size:12px'>Market data as of {datetime.now().astimezone(pytz.timezone('America/New_York')).strftime('%A')} {datetime.now().astimezone(pytz.timezone('America/New_York')).strftime('%-I:%M %p')} ET</span></i><br><span style='font-size:9px'>Table: Phil Rosen, Opening Bell Daily • Source: Yahoo Finance</span>",
            showarrow=False,
            font=dict(color="gray", size=10),
            xref="paper",
            yref="paper",
            xanchor="left",
            yanchor="bottom",
            align="left"
        )

        # Add a footer with data source information and logo on the same line
        image_path = Path(__file__).parent.resolve() / "static" / "obd.png"
        
        # Add logo on the right if available
        if image_path.exists():
            # Use the already imported base64 module
            with open(image_path, "rb") as img_file:
                encoded_image = base64.b64encode(img_file.read()).decode('utf-8')
                img_src = f"data:image/png;base64,{encoded_image}"
            
            fig.add_layout_image(
                dict(
                    source=img_src,
                    xref="paper",
                    yref="paper",
                    x=1.01,  # Changed from 0.98 to 1.0 to move it closer to the right side
                    y=-0.05,  # Aligned with the annotation y-position
                    sizex=0.18,
                    sizey=0.15,
                    xanchor="right", 
                    yanchor="bottom",
                    layer="above",
                    opacity=1.0,
                )
            )
        else:
            print(f"Image not found at: {image_path}")

        # return the plotly json
        return json.loads(fig.to_json())
    
    except Exception as e:
        print(f"Market snapshot error: {str(e)}")
        return JSONResponse(
            content={"error": str(e)}, 
            status_code=500
        )