"""Run corpus audit and weak-label CPU pilot; use explicit task labels."""
import argparse,json
def main():
    p=argparse.ArgumentParser();p.add_argument("task",choices=["audit","weak-pilot"])
    p.add_argument("--archive",required=True);p.add_argument("--output",default="outputs")
    a=p.parse_args()
    if a.task=="audit":
        from glycopath_research.corpus import audit_archive
        r=audit_archive(a.archive,a.output)
    else:
        from glycopath_research.weak_pilot import pilot
        r=pilot(a.archive,a.output)
    print(json.dumps(r,ensure_ascii=False,default=str)[:8000])
if __name__=="__main__":main()
