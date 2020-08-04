import yaml as ym
import pandas as pd
import os
import subprocess
import math
import pathlib
import argparse

from datetime import datetime

now = datetime.now()

def roundup(x, interval):
    return int(math.ceil(x / interval)) * interval

path = 'yaml'
c_path = pathlib.Path(__file__).parent.absolute()
parser = argparse.ArgumentParser(description='Generate kubernetes suggested resources reports.')
parser.add_argument('Namespace',
                   metavar='namespace',
                   type=str,
                   help='namespace to search for VPAs and Deployments')

parser.add_argument('--report', action='store_true')

def main():
    args = parser.parse_args()
    namespace = f'-n {args.Namespace}'
    cluster_contexts = str(subprocess.check_output('kubectl config get-contexts --no-headers -o name', shell=True)).strip("b'").split('\\n')
    if not args.report:
        pathlib.Path(f'{c_path}/yaml').mkdir(parents=True, exist_ok=True)
        for cluster in cluster_contexts:
            os.system(f'kubectl config use-context {cluster}')
            os.system(f'kubectl get vpa,deployment {namespace} -o yaml > {c_path}/{path}/{cluster}.yaml')
    for file_name in os.listdir(path):
        report_string = ""
        with open(f'yaml/{file_name}') as file:
            c_file = ym.load(file, Loader=ym.FullLoader)
            if c_file is None:
                continue
            items = c_file["items"]
            report_string = f"# {file_name.replace('.yaml', '')} Resource Report - {now.strftime('%m/%d/%Y %H:%M:%S')}\n"
            report_dict = {}
            for item in items:
                item_string = ""
                name = item["metadata"]["name"]
                try:
                    report_dict[name]
                except KeyError:
                    report_dict[name] = {}
                print(f'Building report for {name}...')
                if item["kind"] == "VerticalPodAutoscaler":
                    try:
                        cont_rec = item["status"]["recommendation"]["containerRecommendations"]
                        for rec in cont_rec:
                            item_string += f'Container: {rec["containerName"]}\n'
                            limit_cpu = rec["upperBound"]["cpu"]
                            item_string += f'- **Recommended CPU**: {limit_cpu}\n'

                            limit_mem = rec["upperBound"]["memory"]
                            if 'k' in limit_mem:
                                limit_mem = limit_mem.replace('k', "")
                                limit_mem = roundup(int(limit_mem)/1000, 25)
                            else:
                                limit_mem = roundup(int(limit_mem)/1000000, 25)
                            item_string += f'- **Recommended Memory**: {limit_mem}M\n'
                            report_dict[name]["VPA"] = item_string
                    except KeyError:
                        pass
                elif item["kind"] == "Deployment":
                    cont_rec = item["spec"]["template"]["spec"]["containers"]
                    for rec in cont_rec:
                        resources = rec["resources"]
                        item_string += f'Container: {rec["name"]}\n'
                        item_string += f'- **Current CPU**: {resources["limits"]["cpu"]}\n'
                        # item_string += f'\t- Limits: {resources["limits"]["cpu"]}\n'
                        # item_string += f'\t- Requests: {resources["requests"]["cpu"]}\n'

                        item_string += f'- **Current Memory**: {resources["limits"]["memory"]}\n'
                        # item_string += f'\t- Limits: {resources["limits"]["memory"]}\n'
                        # item_string += f'\t- Requests: {resources["requests"]["memory"]}\n'
                        report_dict[name]["Deployment"] = item_string
            for name, info in report_dict.items():
                try:
                    report_string += f"## {name}\n"
                    report_string += f'### Current Resources:\n{info["Deployment"]}\n'
                    report_string += f'### Suggested Resources:\n{info["VPA"]}'
                    report_string += '---\n'
                except KeyError:
                    pass

            c_time_file = now.strftime("%m_%d_%Y_%H_%M")
            pathlib.Path(f'{c_path}/output/{c_time_file}').mkdir(parents=True, exist_ok=True)
            report = open(f'output/{c_time_file}/{file_name.replace(".yaml", "")}.md', 'w')
            report.write(report_string)
            report.close()


if __name__ == "__main__":
    main()
