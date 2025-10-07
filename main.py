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
        # Debug: Print received parameters
        print(f"FRED Series Parameters:")
        print(f"  symbols: {symbols}")
        print(f"  start_date: {start_date}")
        print(f"  end_date: {end_date}")
        print(f"  limit: {limit}")
        print(f"  frequency: {frequency}")
        print(f"  transform: {transform}")
        print(f"  aggregation_method: {aggregation_method}")
        print(f"  theme: {theme}")
        
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
        
        # Prepare kwargs for OpenBB call
        fred_kwargs = {
            "symbol": symbol_list,
            "provider": "fred"
        }
        
        # Add parameters with proper validation
        if limit and limit > 0:
            fred_kwargs["limit"] = limit
            
        if aggregation_method and aggregation_method != "":
            fred_kwargs["aggregation_method"] = aggregation_method
            
        # Handle date parameters - they can be None, empty string, or actual dates
        if start_date and str(start_date).strip() not in ["", "null", "none", "None"]:
            fred_kwargs["start_date"] = start_date
            
        if end_date and str(end_date).strip() not in ["", "null", "none", "None"]:
            fred_kwargs["end_date"] = end_date
            
        if frequency and frequency != "" and frequency != "null":
            fred_kwargs["frequency"] = frequency
            
        if transform and transform != "" and transform != "null":
            fred_kwargs["transform"] = transform
            
        if fred_api_key:
            fred_kwargs["api_key"] = fred_api_key
        
        # Debug: Print final kwargs
        print(f"OpenBB kwargs: {fred_kwargs}")
        
        # Get FRED series data using OpenBB with better error handling
        try:
            result = obb.economy.fred_series(**fred_kwargs)
            df = result.to_df()
        except Exception as obb_error:
            error_msg = str(obb_error)
            print(f"OpenBB Exception caught: {error_msg}")
            
            if "Results not found" in error_msg or "No data" in error_msg:
                return JSONResponse(
                    content={
                        "error": f"No data found for symbols {', '.join(symbol_list)} with the specified parameters.",
                        "suggestions": [
                            "Try using a longer date range (e.g., 1-2 years)",
                            "Remove frequency conversion (annual data may not be available for short periods)", 
                            "Try different transform options or use raw data",
                            "Check if the FRED series symbols are correct (PCENOW, RPI)",
                            "Some series may not have daily/recent data"
                        ],
                        "parameters_used": {
                            "symbols": symbol_list,
                            "start_date": start_date,
                            "end_date": end_date,
                            "frequency": frequency,
                            "transform": transform,
                            "aggregation_method": aggregation_method
                        }
                    }, 
                    status_code=404
                )
            else:
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
        fig.update_layout(
            title="",
            margin=dict(l=20, r=20, t=10, b=80),  # Increased bottom margin for footnote
            paper_bgcolor='#F4FEFF',
            plot_bgcolor='#F4FEFF',
            dragmode=False,
            font=dict(color=text_color),
            xaxis=dict(
                gridcolor=grid_color,
                tickfont=dict(color=text_color)
            ),
            yaxis=dict(
                gridcolor=grid_color,
                tickfont=dict(color=text_color)
            ),
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="center",
                x=0.5,
                font=dict(color=text_color)
            )
        )
        
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
                    x=0.5,
                    y=0.5,
                    sizex=0.4,  # 2x bigger (was 0.2)
                    sizey=0.4,  # 2x bigger (was 0.2)
                    xanchor="center", 
                    yanchor="middle",
                    layer="below",
                    opacity=0.3,  # More visible (was 0.1)
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