import csv
import logging
from calendar import month_name
from itertools import groupby
from operator import itemgetter
from statistics import mean

import click
import requests

URL = 'https://api.worldweatheronline.com/premium/v1/weather.ashx'

logger = logging.getLogger(__name__)


@click.command()
@click.argument('from_month', type=int, required=True)
@click.argument('to_month', type=int, required=True)
@click.argument('places', nargs=-1, required=True)
@click.option('-k', '--api-key', envvar='API_KEY', required=True, help='API key for World Weather Online')
@click.option('-o', '--output-file', default='-', help='a CSV file to write',
              type=click.Path(dir_okay=False, writable=True, resolve_path=True, allow_dash=True))
@click.pass_context
def main(ctx, from_month, to_month, places, api_key, output_file):
    logger.info('Using API URL "%s"', URL)
    session = requests.Session()
    responses = {
        place: session.get(URL, params={
            'format': 'json',
            'key': api_key,
            'q': place,
            'mca': 'yes',
            'fx': 'no',
            'cc': 'no',
        }).json()
        for place in places
    }
    place_errors = {
        place: [error['msg'] for error in response['data']['error']]
        for place, response in responses.items()
        if 'error' in response['data']
    }
    for place, errors in place_errors.items():
        for error in errors:
            logger.error('Error for "%s": %s', place, error)

    if place_errors:
        ctx.exit(1)

    place_data = {
        place: (
            response['data']['request'][0],
            response['data']['ClimateAverages'][0]['month']
        )
        for place, response in responses.items()
    }

    if to_month < from_month:
        month_range = [month for _range in (range(from_month, 13), range(1, to_month + 1)) for month in _range]
    else:
        month_range = list(range(from_month, to_month + 1))

    if from_month == to_month:
        logger.info('Getting data for %s', month_name[from_month])
    else:
        logger.info('Averaging over %s and %s',
                    ', '.join(month_name[i] for i in month_range[:-1]),
                    month_name[month_range[-1]])

    month_data = (
        (place, f'{request["query"]} ({request["type"]})',
         month['name'], month['absMaxTemp'], month['avgMinTemp'], month['avgDailyRainfall'])
        for place, (request, data) in place_data.items()
        for month in data
        if int(month['index']) in month_range
    )
    grouped_data = (
        (month, list(group))
        for month, group in groupby(month_data, itemgetter(0, 1))
    )
    avg_data = {
        place: tuple(
            mean(float(month[i]) for month in data)
            for i in (3, 4, 5)
        ) for place, data in grouped_data
    }
    logger.info('Writing output...')
    with open(output_file, 'w', newline='') as csv_file:
        writer = csv.writer(csv_file)
        writer.writerow(('Search Term', 'Place', 'Max Temperature', 'Min Temperature', 'Average Rainfall'))
        writer.writerows((*place, *data) for place, data in avg_data.items())

    logger.info('Done')


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format='%(levelname)8s: %(message)s')
    main()
