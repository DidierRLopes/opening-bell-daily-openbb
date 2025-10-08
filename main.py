import os
# Fix for Yahoo Finance session issue
os.environ['YFINANCE_BYPASS_CURL_ADAPTER'] = '1'

import json
from pathlib import Path
import pandas as pd
import requests
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import plotly.graph_objects as go
# from plotly_templates import dark_template
import pandas as pd
from openbb import obb
from fredapi import Fred
from datetime import datetime
from fastapi.staticfiles import StaticFiles
import pytz
import base64


app = FastAPI()

app.mount("/static", StaticFiles(directory="static"), name="static")

origins = [
    "https://pro.openbb.co",
    "https://pro.openbb.dev",
    "https://excel.openbb.co",
    "http://localhost:1420",
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


@app.get("/apps.json")
def get_apps():
    """Apps configuration file for the OpenBB Custom Backend"""
    return JSONResponse(
        content=json.load((Path(__file__).parent.resolve() / "apps.json").open())
    )


@app.get("/health")
def health_check():
    return {"status": "healthy"}


@app.get("/market_snapshot")
def get_market_snapshot(raw: bool = False):
    """Get current market snapshot of major indices and assets"""
    
    try:
        # Define the symbols we want to track
        symbols = {
            "^DJI": "DJIA",
            "^GSPC": "S&P 500", 
            "^IXIC": "NASDAQ*",
            "^RUT": "Russell 2K",
            "MAGS": "Magnificent 7 ETF**",
            "ACWI": "MSCI All World",
            "BTC-USD": "Bitcoin",
            "GC=F": "Gold",
            "SLV": "Silver",
            "BZ=F": "Brent Crude",
            "^TNX": "10-Year",
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

        if raw:
            return results

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
        header_positions = [0.02, 0.42, 0.72, 1]  # Give more space to first column with consistent left margin
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
                font=dict(size=16, color='black', family="Arial"),
                xref="paper",
                yref="paper",
                xanchor="left",
                yanchor="middle",
                align="left"
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
            
            # Add value text with special formatting
            value_text = ""
            if row['Index'] == "Gold":
                value_text = f"${row['Value']:,} per ounce"
            elif row['Index'] == "Silver":
                value_text = f"${row['Value']:,} per ounce"
            elif row['Index'] == "Bitcoin":
                value_text = f"${row['Value']:,}"
            elif row['Index'] == "Brent Crude":
                value_text = f"${row['Value']:,} a barrel"
            elif row['Index'] == "10-Year":
                value_text = f"{row['Value']:.2f}%"
            elif row['Index'] == "Magnificent 7 ETF**":
                value_text = f"${row['Value']:,}"
            elif row['Index'] == "MSCI All World":
                value_text = f"${row['Value']:,}"
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
            text=f"<i><span style='font-size:12px'>Market data as of {datetime.now().astimezone(pytz.timezone('America/New_York')).strftime('%A')} {datetime.now().astimezone(pytz.timezone('America/New_York')).strftime('%-I:%M %p')} ET, *Nasdaq Composite, **Roundhill MAGS ETF</span></i><br><span style='font-size:9px'>Table: Phil Rosen, Opening Bell Daily • Source: Yahoo Finance</span>",
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


@app.get("/fred_series")
def get_fred_series(
    request: Request, 
    symbols: str = "PCENOW,RPI",
    chart_title: str = "",
    start_date: str = None,
    end_date: str = None,
    limit: int = 100000,
    frequency: str = None,
    transform: str = None,
    aggregation_method: str = "eop",
    theme: str = "dark"
):
    """Get FRED series data with Plotly visualization"""
    
    try:
        
        # Split symbols string into list
        symbol_list = [s.strip() for s in symbols.split(',')]
        
        # Validate date ranges
        today = datetime.now().date()
        
        if start_date and str(start_date).strip() not in ["", "null", "none", "None"]:
            try:
                start_dt = datetime.strptime(start_date, "%Y-%m-%d").date()
                if start_dt > today:
                    return JSONResponse(
                        content={"error": f"Start date ({start_date}) cannot be in the future. Today is {today}"}, 
                        status_code=400
                    )
            except ValueError:
                return JSONResponse(
                    content={"error": f"Invalid start date format: {start_date}. Use YYYY-MM-DD"}, 
                    status_code=400
                )
                
        if end_date and str(end_date).strip() not in ["", "null", "none", "None"]:
            try:
                end_dt = datetime.strptime(end_date, "%Y-%m-%d").date()
                if end_dt > today:
                    return JSONResponse(
                        content={"error": f"End date ({end_date}) cannot be in the future. Today is {today}"}, 
                        status_code=400
                    )
            except ValueError:
                return JSONResponse(
                    content={"error": f"Invalid end date format: {end_date}. Use YYYY-MM-DD"}, 
                    status_code=400
                )
        
        # Get FRED API key from custom header
        fred_api_key = request.headers.get("X-FRED-API-KEY")
        if not fred_api_key:
            return JSONResponse(
                content={"error": "FRED API key is required. Please provide X-FRED-API-KEY header."}, 
                status_code=400
            )
        
        # Initialize FRED API client
        try:
            fred = Fred(api_key=fred_api_key)
        except Exception as e:
            return JSONResponse(
                content={"error": f"Failed to initialize FRED client: {str(e)}"}, 
                status_code=500
            )
        
        # Prepare date parameters
        start_dt = None
        end_dt = None
        
        if start_date and str(start_date).strip() not in ["", "null", "none", "None"]:
            start_dt = start_date
            
        if end_date and str(end_date).strip() not in ["", "null", "none", "None"]:
            end_dt = end_date
        
        # Get FRED series data using fredapi
        try:
            # Collect data for all symbols
            all_series = {}
            
            for symbol in symbol_list:
                try:
                    # Get series data
                    series_data = fred.get_series(
                        symbol, 
                        observation_start=start_dt, 
                        observation_end=end_dt,
                        limit=limit if limit and limit > 0 else None
                    )
                    
                    # Apply frequency conversion if specified
                    if frequency and frequency != "" and frequency != "null":
                        freq_map = {
                            'a': 'YE', 'q': 'QE', 'm': 'ME', 'w': 'W', 'd': 'D'
                        }
                        if frequency in freq_map:
                            if aggregation_method == "avg":
                                series_data = series_data.resample(freq_map[frequency]).mean()
                            elif aggregation_method == "sum":
                                series_data = series_data.resample(freq_map[frequency]).sum()
                            else:  # eop (end of period)
                                series_data = series_data.resample(freq_map[frequency]).last()
                    
                    # Apply transform if specified
                    if transform and transform != "" and transform != "null":
                        if transform == "chg":
                            series_data = series_data.diff()
                        elif transform == "ch1":
                            series_data = series_data.diff(periods=12)  # Change from year ago
                        elif transform == "pch":
                            series_data = series_data.pct_change() * 100
                        elif transform == "pc1":
                            series_data = series_data.pct_change(periods=12) * 100  # Percent change from year ago
                        elif transform == "log":
                            import numpy as np
                            series_data = np.log(series_data)
                    
                    all_series[symbol] = series_data
                    
                except Exception as series_error:
                    print(f"Error fetching {symbol}: {str(series_error)}")
                    continue
            
            if not all_series:
                return JSONResponse(
                    content={
                        "error": f"No data found for any symbols: {', '.join(symbol_list)}",
                        "suggestions": [
                            "Check if the FRED series symbols are correct",
                            "Try a different date range",
                            "Some series may not have recent data"
                        ]
                    }, 
                    status_code=404
                )
            
            # Combine all series into a DataFrame
            df = pd.DataFrame(all_series)
            
        except Exception as fred_error:
            error_msg = str(fred_error)
            print(f"FRED API Exception caught: {error_msg}")
            return JSONResponse(
                content={"error": f"FRED API error: {error_msg}"}, 
                status_code=500
            )
        
        if df.empty:
            return JSONResponse(
                content={
                    "error": f"No data returned for symbols {', '.join(symbol_list)}. The series may not exist or may not have data for the specified date range.",
                    "suggestion": "Try using default date range (2 years back) or check if the FRED series symbols are correct."
                }, 
                status_code=404
            )
        
        # Create Plotly figure
        fig = go.Figure()
        
        # Define theme colors
        if theme == "dark":
            bg_color = "#151518"
            text_color = "#FFFFFF"
            grid_color = "rgba(51, 51, 51, 0.3)"
            colors = ["#FF8000", "#2D9BF0", "#00AA44", "#FF4444", "#AA44FF"]
        else:
            bg_color = "#FFFFFF"
            text_color = "#333333"
            grid_color = "rgba(221, 221, 221, 0.3)"
            colors = ["#2E5090", "#00AA44", "#FF6B35", "#8A2BE2", "#DC143C"]
        
        # Add traces for each symbol
        for i, symbol in enumerate(symbol_list):
            if symbol in df.columns:
                fig.add_trace(go.Scatter(
                    x=df.index,
                    y=df[symbol],
                    mode='lines',
                    name=symbol,
                    line=dict(
                        width=2,
                        color=colors[i % len(colors)]
                    )
                ))
        
        # Update layout with theme - matching market_snapshot styling
        layout_config = {
            "margin": dict(l=20, r=20, t=10 if not chart_title else 50, b=80),  # Adjust top margin if title exists
            "paper_bgcolor": 'white',
            "plot_bgcolor": 'white',
            "dragmode": False,
            "font": dict(color=text_color),
            "xaxis": dict(
                gridcolor=grid_color,
                tickfont=dict(color=text_color)
            ),
            "yaxis": dict(
                gridcolor=grid_color,
                tickfont=dict(color=text_color)
            ),
            "legend": dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="right",
                x=1.0,
                font=dict(color=text_color)
            )
        }
        
        # Add title if provided
        if chart_title and chart_title.strip():
            layout_config["title"] = dict(
                text=chart_title,
                x=0.02,  # Small left margin
                xanchor="left",
                font=dict(size=20, color=text_color)
            )
        else:
            layout_config["title"] = ""
            
        fig.update_layout(**layout_config)
        
        # Add watermark logo in center of plot
        image_path = Path(__file__).parent.resolve() / "static" / "obd.png"
        if image_path.exists():
            with open(image_path, "rb") as img_file:
                encoded_image = base64.b64encode(img_file.read()).decode('utf-8')
                img_src = f"data:image/png;base64,{encoded_image}"
            
            fig.add_layout_image(
                dict(
                    source=img_src,
                    xref="paper",
                    yref="paper",
                    x=1.01,
                    y=-0.35,
                    sizex=0.30,
                    sizey=0.27,
                    xanchor="right", 
                    yanchor="bottom",
                    layer="above",
                    opacity=1.0,
                )
            )
        
        # Add data source annotation below x-axis
        fig.add_annotation(
            x=0,
            y=-0.15,  # Position below x-axis
            text=f"<i><span style='font-size:12px'>FRED Economic Data: {', '.join(symbol_list)}</span></i><br><span style='font-size:9px'>Chart: Opening Bell Daily • Source: Federal Reserve Economic Data (FRED)</span>",
            showarrow=False,
            font=dict(color="gray", size=10),
            xref="paper",
            yref="paper",
            xanchor="left",
            yanchor="top",
            align="left"
        )
        
        return json.loads(fig.to_json())
    
    except Exception as e:
        print(f"FRED series error: {str(e)}")
        return JSONResponse(
            content={"error": str(e)}, 
            status_code=500
        )


@app.get("/market_chart")
def get_market_chart(
    request: Request,
    symbol: str = "^GSPC",
    chart_title: str = "",
    start_date: str = None,
    transform: str = "",
    theme: str = "dark"
):
    """Get YFinance chart data with Plotly visualization"""
    
    try:
        # Split symbols string into list for multi-selection support
        symbol_list = [s.strip() for s in symbol.split(',')]
        
        # Debug: Print received parameters
        
        # Validate date ranges
        today = datetime.now().date()
        
        if start_date and str(start_date).strip() not in ["", "null", "none", "None"]:
            try:
                start_dt = datetime.strptime(start_date, "%Y-%m-%d").date()
                if start_dt > today:
                    return JSONResponse(
                        content={"error": f"Start date ({start_date}) cannot be in the future. Today is {today}"}, 
                        status_code=400
                    )
            except ValueError:
                return JSONResponse(
                    content={"error": f"Invalid start date format: {start_date}. Use YYYY-MM-DD"}, 
                    status_code=400
                )
        
        # Create Plotly figure
        fig = go.Figure()
        
        # Define theme colors
        if theme == "dark":
            text_color = "#FFFFFF"
            grid_color = "rgba(51, 51, 51, 0.3)"
            colors = ["#FF8000", "#2D9BF0", "#00AA44", "#FF4444", "#AA44FF", "#FF8844", "#44FF88"]
        else:
            text_color = "#333333"
            grid_color = "rgba(221, 221, 221, 0.3)"
            colors = ["#2E5090", "#00AA44", "#FF6B35", "#8A2BE2", "#DC143C", "#228B22", "#FF1493"]
        
        successful_symbols = []
        failed_symbols = []
        
        # Process each symbol
        for i, sym in enumerate(symbol_list):
            try:
                # Prepare kwargs for OpenBB call
                yf_kwargs = {
                    "symbol": sym,
                    "provider": "yfinance"
                }
                
                # Add start date if provided
                if start_date and str(start_date).strip() not in ["", "null", "none", "None"]:
                    yf_kwargs["start_date"] = start_date
                
                
                # Get YFinance data using OpenBB
                try:
                    result = obb.equity.price.historical(**yf_kwargs)
                    df = result.to_df()
                except Exception as obb_error:
                    
                    # Try fallback approach
                    try:
                        fallback_kwargs = {"symbol": sym, "provider": "yfinance"}
                        result = obb.equity.price.historical(**fallback_kwargs)
                        df = result.to_df()
                        
                        # Filter by start_date if provided
                        if start_date and str(start_date).strip() not in ["", "null", "none", "None"]:
                            df = df[df.index >= start_date]
                            
                    except Exception as fallback_error:
                        failed_symbols.append(sym)
                        continue
                
                if df.empty:
                    failed_symbols.append(sym)
                    continue
                
                # Determine which price column to use
                price_column = None
                for col in ['close', 'Close', 'adj_close', 'Adj Close']:
                    if col in df.columns:
                        price_column = col
                        break
                
                if price_column is None:
                    failed_symbols.append(sym)
                    continue
                
                
                # Apply transform if specified
                if transform and transform.strip() and transform != "none":
                    if transform == "pct_change":
                        df[price_column] = df[price_column].pct_change() * 100
                    elif transform == "cumulative_return":
                        df[price_column] = ((df[price_column] / df[price_column].iloc[0]) - 1) * 100
                    elif transform == "log_return":
                        import numpy as np
                        df[price_column] = np.log(df[price_column] / df[price_column].shift(1)) * 100
                
                # Add price line trace for this symbol
                fig.add_trace(go.Scatter(
                    x=df.index,
                    y=df[price_column],
                    mode='lines',
                    name=sym,
                    line=dict(
                        width=2,
                        color=colors[i % len(colors)]
                    )
                ))
                
                successful_symbols.append(sym)
                
            except Exception as symbol_error:
                failed_symbols.append(sym)
                continue
        
        # Check if any symbols were successful
        if not successful_symbols:
            return JSONResponse(
                content={
                    "error": f"No data found for any of the symbols: {', '.join(symbol_list)}.",
                    "failed_symbols": failed_symbols,
                    "suggestions": [
                        "Check if the symbols are correct",
                        "Try a different date range",
                        "Some symbols may not have historical data available"
                    ]
                }, 
                status_code=404
            )
        
        # Update layout with theme - matching FRED styling
        layout_config = {
            "margin": dict(l=20, r=20, t=10 if not chart_title else 50, b=80),
            "paper_bgcolor": 'white',
            "plot_bgcolor": 'white',
            "dragmode": False,
            "font": dict(color=text_color),
            "xaxis": dict(
                gridcolor=grid_color,
                tickfont=dict(color=text_color)
            ),
            "yaxis": dict(
                gridcolor=grid_color,
                tickfont=dict(color=text_color)
            ),
            "legend": dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="right",
                x=1.0,
                font=dict(color=text_color)
            )
        }
        
        # Add title if provided
        if chart_title and chart_title.strip():
            layout_config["title"] = dict(
                text=chart_title,
                x=0.02,
                xanchor="left",
                font=dict(size=20, color=text_color)
            )
        else:
            layout_config["title"] = ""
            
        fig.update_layout(**layout_config)
        
        # Add watermark logo in center of plot
        image_path = Path(__file__).parent.resolve() / "static" / "obd.png"
        if image_path.exists():
            with open(image_path, "rb") as img_file:
                encoded_image = base64.b64encode(img_file.read()).decode('utf-8')
                img_src = f"data:image/png;base64,{encoded_image}"
            
            fig.add_layout_image(
                dict(
                    source=img_src,
                    xref="paper",
                    yref="paper",
                    x=1.01,
                    y=-0.35,
                    sizex=0.30,
                    sizey=0.27,
                    xanchor="right", 
                    yanchor="bottom",
                    layer="above",
                    opacity=1.0,
                )
            )
        
        # Add data source annotation below x-axis
        transform_text = f" ({transform})" if transform and transform != "none" else ""
        symbols_text = ', '.join(successful_symbols)
        
        # Add warning about failed symbols if any
        warning_text = ""
        if failed_symbols:
            warning_text = f"<br><span style='color:orange;font-size:8px'>⚠ Failed to load: {', '.join(failed_symbols)}</span>"
        
        fig.add_annotation(
            x=0,
            y=-0.15,
            text=f"<i><span style='font-size:12px'>Financial Data: {symbols_text}{transform_text}</span></i><br><span style='font-size:9px'>Chart: Opening Bell Daily • Source: Yahoo Finance</span>{warning_text}",
            showarrow=False,
            font=dict(color="gray", size=10),
            xref="paper",
            yref="paper",
            xanchor="left",
            yanchor="top",
            align="left"
        )
        
        return json.loads(fig.to_json())
    
    except Exception as e:
        print(f"Market chart error: {str(e)}")
        return JSONResponse(
            content={"error": str(e)}, 
            status_code=500
        )


@app.get("/yfinance_chart")
def get_yfinance_chart(
    request: Request,
    symbols: str = "^GSPC",
    chart_title: str = "",
    start_date: str = None,
    transform: str = ""
):
    try:
        # Get theme from request headers
        theme = request.headers.get("theme", "dark")
        
        # Validate start_date
        if start_date:
            if start_date.startswith("$currentDate"):
                # Handle OpenBB date modifiers like "$currentDate-1y"
                try:
                    modifier = start_date.replace("$currentDate", "").strip()
                    if modifier.startswith("-"):
                        # Parse modifier like "-1y", "-2m", "-30d"
                        amount = int(modifier[1:-1])
                        unit = modifier[-1].lower()
                        
                        from datetime import datetime, timedelta
                        import dateutil.relativedelta
                        
                        current_date = datetime.now()
                        if unit == 'y':
                            start_date = (current_date - dateutil.relativedelta.relativedelta(years=amount)).strftime('%Y-%m-%d')
                        elif unit == 'm':
                            start_date = (current_date - dateutil.relativedelta.relativedelta(months=amount)).strftime('%Y-%m-%d')
                        elif unit == 'd':
                            start_date = (current_date - timedelta(days=amount)).strftime('%Y-%m-%d')
                        else:
                            start_date = (current_date - dateutil.relativedelta.relativedelta(years=1)).strftime('%Y-%m-%d')
                    else:
                        start_date = datetime.now().strftime('%Y-%m-%d')
                except:
                    start_date = (datetime.now() - dateutil.relativedelta.relativedelta(years=1)).strftime('%Y-%m-%d')
            else:
                # Validate date format
                try:
                    from datetime import datetime
                    datetime.strptime(start_date, '%Y-%m-%d')
                    # Check if date is not in the future
                    if datetime.strptime(start_date, '%Y-%m-%d') > datetime.now():
                        start_date = datetime.now().strftime('%Y-%m-%d')
                except ValueError:
                    start_date = None
        
        if not start_date:
            from datetime import datetime
            import dateutil.relativedelta
            start_date = (datetime.now() - dateutil.relativedelta.relativedelta(years=1)).strftime('%Y-%m-%d')
        
        # Parse symbols - handle comma-separated input
        symbol_list = [s.strip().upper() for s in symbols.split(',') if s.strip()]
        if not symbol_list:
            symbol_list = ['^GSPC']  # Default fallback
        
        all_data = []
        failed_symbols = []
        
        # Process each symbol
        for symbol in symbol_list:
            try:
                # Get historical data using OpenBB
                data = obb.equity.price.historical(
                    symbol=symbol,
                    start_date=start_date,
                    provider="yfinance"
                )
                
                if data is None or len(data.results) == 0:
                    failed_symbols.append(symbol)
                    continue
                
                # Convert to DataFrame
                df = data.to_df()
                
                if df is None or df.empty:
                    failed_symbols.append(symbol)
                    continue
                
                # Find the price column - check for different possible column names
                price_column = None
                possible_columns = ['close', 'Close', 'adj_close', 'Adj Close', 'price', 'Price']
                for col in possible_columns:
                    if col in df.columns:
                        price_column = col
                        break
                
                if price_column is None:
                    # If no standard price column found, use the last numeric column
                    numeric_cols = df.select_dtypes(include=['float64', 'int64']).columns
                    if len(numeric_cols) > 0:
                        price_column = numeric_cols[-1]
                    else:
                        failed_symbols.append(symbol)
                        continue
                
                # Apply transformations
                if transform == "pct_change":
                    df[price_column] = df[price_column].pct_change() * 100
                    df = df.dropna()
                elif transform == "cumulative_return":
                    df[price_column] = (df[price_column] / df[price_column].iloc[0] - 1) * 100
                elif transform == "log_return":
                    import numpy as np
                    df[price_column] = np.log(df[price_column] / df[price_column].shift(1)) * 100
                    df = df.dropna()
                
                # Add symbol identifier and store data
                df['symbol'] = symbol
                all_data.append(df)
                
            except Exception as e:
                failed_symbols.append(symbol)
                continue
        
        if not all_data:
            return JSONResponse(
                content={"error": f"No valid data found for any symbols: {', '.join(symbol_list)}"}, 
                status_code=404
            )
        
        # Create Plotly chart
        import plotly.graph_objects as go
        from plotly.subplots import make_subplots
        import plotly.io as pio
        
        fig = go.Figure()
        
        # Add traces for each symbol
        for df in all_data:
            symbol = df['symbol'].iloc[0]
            
            # Find the price column again for this dataframe
            price_column = None
            possible_columns = ['close', 'Close', 'adj_close', 'Adj Close', 'price', 'Price']
            for col in possible_columns:
                if col in df.columns and col != 'symbol':
                    price_column = col
                    break
            
            if price_column is None:
                numeric_cols = df.select_dtypes(include=['float64', 'int64']).columns
                numeric_cols = [col for col in numeric_cols if col != 'symbol']
                if len(numeric_cols) > 0:
                    price_column = numeric_cols[-1]
                else:
                    continue
            
            fig.add_trace(go.Scatter(
                x=df.index,
                y=df[price_column],
                mode='lines',
                name=symbol,
                line=dict(width=2)
            ))
        
        # Determine y-axis title based on transform
        if transform == "pct_change":
            y_title = "Percent Change (%)"
        elif transform == "cumulative_return":
            y_title = "Cumulative Return (%)"
        elif transform == "log_return":
            y_title = "Log Return (%)"
        else:
            y_title = "Price"
        
        # Configure layout based on theme (matching market chart exactly)
        if theme == "light":
            text_color = "black"
            grid_color = "#E5E5E5"
        else:
            text_color = "black"  # Use black text on white background
            grid_color = "#E5E5E5"
        
        # Update layout with theme - matching market chart styling exactly
        layout_config = {
            "margin": dict(l=20, r=20, t=10 if not chart_title else 50, b=80),  # Match market chart
            "paper_bgcolor": 'white',
            "plot_bgcolor": 'white',
            "dragmode": False,
            "font": dict(color=text_color),
            "xaxis": dict(
                gridcolor=grid_color,
                tickfont=dict(color=text_color)
            ),
            "yaxis": dict(
                gridcolor=grid_color,
                tickfont=dict(color=text_color)
            ),
            "legend": dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="right",
                x=1.0,
                font=dict(color=text_color)
            )
        }
        
        # Add title if provided
        if chart_title and chart_title.strip():
            layout_config["title"] = dict(
                text=chart_title,
                x=0.02,
                xanchor="left",
                font=dict(size=20, color=text_color)
            )
        else:
            layout_config["title"] = ""
            
        fig.update_layout(**layout_config)
        
        # Add watermark logo in same position as market chart
        from pathlib import Path
        import base64
        image_path = Path(__file__).parent.resolve() / "static" / "obd.png"
        if image_path.exists():
            with open(image_path, "rb") as img_file:
                encoded_image = base64.b64encode(img_file.read()).decode('utf-8')
                img_src = f"data:image/png;base64,{encoded_image}"
            
            fig.add_layout_image(
                dict(
                    source=img_src,
                    xref="paper",
                    yref="paper",
                    x=1.01,
                    y=-0.35,  # Match market chart position
                    sizex=0.30,  # Match market chart size
                    sizey=0.27,  # Match market chart size
                    xanchor="right",  # Match market chart anchor
                    yanchor="bottom",
                    layer="above",
                    opacity=1.0,
                )
            )
        
        # Add data source annotation below x-axis (matching market chart)
        transform_text = f" ({transform})" if transform and transform != "none" else ""
        symbols_text = ', '.join([s.strip() for s in symbols.split(',') if s.strip()])
        
        # Add warning about failed symbols if any
        warning_text = ""
        if failed_symbols:
            warning_text = f"<br><span style='color:orange;font-size:8px'>⚠ Failed to load: {', '.join(failed_symbols)}</span>"
        
        fig.add_annotation(
            x=0,
            y=-0.15,  # Match market chart position
            text=f"<i><span style='font-size:12px'>Financial Data: {symbols_text}{transform_text}</span></i><br><span style='font-size:9px'>Chart: Opening Bell Daily • Source: Yahoo Finance</span>{warning_text}",
            showarrow=False,
            font=dict(color="gray", size=10),
            xref="paper",
            yref="paper",
            xanchor="left",
            yanchor="top",
            align="left"  # Match market chart
        )
        
        # Return the chart in the same format as other widgets
        import json
        return json.loads(fig.to_json())
    
    except Exception as e:
        print(f"YFinance chart error: {str(e)}")
        return JSONResponse(
            content={"error": str(e)}, 
            status_code=500
        )