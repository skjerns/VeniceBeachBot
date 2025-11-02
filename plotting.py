# -*- coding: utf-8 -*-
"""
Created on Tue Feb 22 17:02:37 2022

visualizes current active users in venice beach location

@author: Simon Kern
"""
import time
import os
import datetime
import matplotlib
debug = 'arm' not in os.uname().machine
#if not debug:
#    matplotlib.use('Agg')
from datetime import timedelta
from io import BytesIO
import numpy as np
import matplotlib.dates as mdates
import pandas as pd
import utils
import matplotlib.pyplot as plt
import stimer
from telebot.types import InputFile, ForceReply

firsthour = 5

def highlight_now(ax=None, **kwargs):
    now = datetime.datetime.now()
    x = now.hour-firsthour
    y = now.weekday()
    rect = plt.Rectangle((x-.5, y-.5), 1,1, fill=False, **kwargs)
    ax = ax or plt.gca()
    ax.add_patch(rect)
    return


def shade_leftover_hours(ax=None, **kwargs):
    now = datetime.datetime.now()
    x = now.hour-firsthour
    y = now.weekday()
    ax = ax or plt.gca()

    for h in range(x+1, 24-firsthour):
        rect = plt.Rectangle((h-.5, y-.5), 1,1, fill=False, alpha=0.75,
                             hatch=r"\\\\", edgecolor='gray', linestyle='--')
        ax.add_patch(rect)
    return

# @profile
def make_plot(studio_id):
    csv_file = os.path.expanduser(f'./data/studio_{studio_id}.csv')
    png_file = os.path.expanduser(f'./data/studio_{studio_id}.png')

    if os.path.exists(png_file) and not debug:
        recent_png = ((time.time()-os.path.getmtime(png_file))<(10*60))
        if recent_png:
            return png_file

    studios = utils.load_studios()
    studio_name = studios.get(str(studio_id), 'Unknown Studio')

    now = datetime.datetime.now()

    df = pd.read_csv(csv_file, sep=';', names=['members', 'max'])
    df.members = df.members.convert_dtypes()
    df['max'] = df['max'].convert_dtypes()
    df['max'].loc[0] = 150
    n_max = max([int(x) for x in df['max'] if str(x).isnumeric()])
    df = df.drop('max', axis=1)
    df[df.members==-1] = np.nan
    df.index = pd.to_datetime(df.index, format='ISO8601').round('5min')
    df = df[~df.index.duplicated()]
    df = df.reindex(pd.date_range(start=df.index.max()-timedelta(weeks=7),
                                  end=df.index.max(),
                                  freq='5min'))
    df = df.astype(float).interpolate(method='linear')

    df_4week = df.loc[df.index > now-timedelta(days=7*4)]  # last four weeks
    week_avg = df_4week.groupby((df_4week.index.dayofweek) * 24 +
                                (df_4week.index.hour)).mean().rename_axis('HourOfWeek')
    week_avg = week_avg.reindex(np.arange(168), fill_value=np.nan)
    week_avg = np.array(week_avg.members).reshape([24, 7], order='F').T.astype(float)


    ######  plot last 4 weeks
    fig = plt.figure(figsize=[6, 8])

    # cmap = sns.color_palette("Spectral", as_cmap=True).reversed()
    cmap1 = plt.get_cmap('Spectral_r')

    colors = [(0.6196078431372549, 0.00392156862745098, 0.25882352941176473, 1.0),
              (0, 0, 0, 1)]
    cmap2 = matplotlib.colors.LinearSegmentedColormap.from_list("", colors, N=256//4)

    colors = np.vstack([[cmap1(x) for x in range(256)],
                        [cmap2(x) for x in range(64)]])
    cmap = matplotlib.colors.LinearSegmentedColormap.from_list("", colors, N=256+64)

    ax = plt.subplot(3, 1, 1)
    img = ax.imshow(week_avg[:,firsthour:], aspect='auto', cmap=cmap,
               vmin=n_max/10, vmax=n_max-n_max/10)
    highlight_now( color='r')
    ax.set_title(f'Durchschnitt letzte 4 Wochen')
    ax.set_xticks(np.arange(24-firsthour), np.arange(firsthour, 24))
    ax.set_yticks(np.arange(7), ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'])

    ax.set_xlabel('Stunde')
    ax.set_ylabel('Wochentag')
    fig.colorbar(img)

    now = datetime.datetime.now()

    df_lastweek = df.loc[df.index > now-timedelta(days=7)] # this is the last week
    lastweek_avg = df_lastweek.groupby((df_lastweek.index.dayofweek) * 24 + (df_lastweek.index.hour)).mean().rename_axis('HourOfWeek')
    lastweek_avg = lastweek_avg.reindex(np.arange(168), fill_value=np.nan)
    lastweek_avg = np.array(lastweek_avg).reshape([-1,  7], order='F').T.astype(float)

    ######  plot last week

    plt.subplot(3, 1, 2)
    plt.imshow(lastweek_avg[:,firsthour:], aspect='auto', cmap=cmap,
               vmin=n_max/10, vmax=n_max-n_max/10)
    shade_leftover_hours()
    highlight_now(color='r')

    plt.title(f'diese Woche')
    plt.xticks(np.arange(24-firsthour), np.arange(firsthour, 24))
    plt.yticks(np.arange(7), ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'])

    plt.xlabel('Stunde')
    plt.ylabel('Wochentag')
    plt.colorbar()

    ######  plot today and forecast
    plt.subplot(3, 1, 3)

    prevh = 2
    nexth = 4
    curr = df.loc[df.index > now+timedelta(hours=-prevh)]
    curr.index = curr.index.round('5min')
    curr = curr.astype('float').interpolate()
    try:
        ppl_now = int(curr.iloc[-1])
    except:
        ppl_now = 0
    plt.plot(curr)

    weeks = []
    last_n = 7
    for w in range(-1, -last_n, -1):
        idx_week = ((df.index > now+timedelta(days=7*w, hours=-prevh)) &
                       (df.index < now+timedelta(days=7*w, hours=+nexth)))
        week = df[idx_week]['members']
        if len(week) > 0:
            weeks.append(week)

    times = pd.date_range(now-timedelta(hours=+prevh), now+timedelta(hours=+nexth), freq='s')
    times = times.round('5min').unique()
    times = times[:len(weeks[-1])]

    weeks = np.array(weeks)
    b = np.zeros([len(weeks),len(max(weeks, key = lambda x: len(x)))])

    plt.plot(times[:len(weeks[0])], np.nanmean(weeks, 0), linestyle='dashed', color='black', alpha=0.5)

    weeksmin = np.nanmin(np.array(weeks), 0)
    weeksmax = np.nanmax(np.array(weeks), 0)
    plt.fill_between(times, weeksmin, weeksmax, color='gray', alpha=0.3)

    xformatter = mdates.DateFormatter('%H:%M')
    plt.gca().xaxis.set_major_formatter(xformatter)
    weeksmaxmax = max(np.nan_to_num(weeksmax.max())*1.5, n_max)
    plt.ylim([0, weeksmaxmax])
    plt.legend(['heute', 'letzte Woche', f'letzte {last_n-1} Wochen'])
    plt.title(f'Jetzt: {int(ppl_now)}/{n_max}')
    plt.suptitle(f'{studio_name}: {int(ppl_now)}/{n_max}')

    plt.grid(which='major', alpha=0.5)
    plt.tight_layout()
    # i/o on the SD card is actually really fast
    # the slow process is the backend and converting to PNG/JPG
    # therefore we can easily save to disk and not to BytesIO w/o perf-loss
    # with stimer:
    plt.savefig(png_file)
    try:
       plt.close(fig)
    except:
       pass
    return png_file

# import pandas as pd
# import numpy as np
# import plotly.graph_objs as go
# import plotly.figure_factory as ff
# from plotly.offline import plot
# import os
# import datetime
# from datetime import timedelta
# import utils  # Assuming utils is a module for utility functions

def plot_with_plotly(studio_id, debug=False):
    csv_file = os.path.expanduser(f'./data/studio_{studio_id}.csv')
    html_file = os.path.expanduser(f'./data/studio_{studio_id}.html')

    if os.path.exists(html_file) and not debug:
        recent_html = ((time.time() - os.path.getmtime(html_file)) < (10 * 60))
        if recent_html:
            return html_file

    studios = utils.load_studios()
    studio_name = studios.get(str(studio_id), 'Unknown Studio')

    # Assume that the remaining Pandas DataFrame processing is correct
    # and produces the necessary week_avg and lastweek_avg DataFrames
    # as well as the timeseries data for the 'today and forecast' plot.

    # ... (data manipulation code from the original function)

    # Create subplots
    fig = make_subplots(rows=3, cols=1, shared_xaxes=True,
                        vertical_spacing=0.02, subplot_titles=('4 Week Average', 'Last Week', 'Today and Forecast'))

    # Heatmap for the 4-week average
    fig.add_trace(
        go.Heatmap(
            z=week_avg,
            x=np.arange(firsthour, 24),  # or equivalent list if "firsthour" is not defined
            y=['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'],
            coloraxis="coloraxis"
        ),
        row=1, col=1
    )

    # Heatmap for the last week
    fig.add_trace(
        go.Heatmap(
            z=lastweek_avg,
            x=np.arange(firsthour, 24),
            y=['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'],
            coloraxis="coloraxis"
        ),
        row=2, col=1
    )

    # Time Series for today and forecast
    # today's data
    fig.add_trace(
        go.Scatter(
            x=curr.index,
            y=curr['members'],
            mode='lines',
            name='Today'
        ),
        row=3, col=1
    )

    # average of last weeks
    fig.add_trace(
        go.Scatter(
            x=times[:len(weeks[0])],
            y=np.nanmean(weeks, axis=0),
            mode='lines',
            name=f'Average of Last {last_n-1} Weeks',
            line=dict(dash='dash')
        ),
        row=3, col=1
    )

    # shaded area for min and max
    fig.add_trace(
        go.Scatter(
            x=np.concatenate([times, times[::-1]]),  # x, then x reversed
            y=np.concatenate([weeksmin, weeksmax[::-1]]),  # upper, then lower reversed
            fill='toself',
            fillcolor='rgba(0,100,80,0.2)',
            line=dict(color='rgba(255,255,255,0)'),
            hoverinfo="skip",
            showlegend=False
        ),
        row=3, col=1
    )

    # Update layout with coloraxis for consistency across heatmaps
    fig.update_layout(
        coloraxis=dict(colorscale='Viridis', cmin=n_max/10, cmax=n_max-n_max/10),
        title_text=f"{studio_name}: {int(ppl_now)}/{n_max}"
    )

    # Update x-axis and y-axis labels, titles, etc.
    fig.update_yaxes(title_text="Day of Week", row=1, col=1)
    fig.update_yaxes(title_text="Day of Week", row=2, col=1)
    fig.update_xaxes(title_text="Hour of Day", row=3, col=1)

    # Output the plot to an HTML file
    plot(fig, filename=html_file, auto_open=False)

    return html_file


if __name__=='__main__':
    debug=True

    with stimer('total plotting'):
        make_plot(42)
