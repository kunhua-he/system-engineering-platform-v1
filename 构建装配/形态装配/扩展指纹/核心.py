"""扩展快照生成与零写检查，不解释模块容器，不改已有专用生成器的归属。"""
import hashlib
import json
from pathlib import Path

生成器相对路径 = '构建装配/形态装配/扩展指纹.py'


def 收集扩展指纹(包目录):
    文件表 = {包目录/'包声明.json'}
    for 通配形状 in ('能力声明/*.json','错误码表/*.json','类型声明/*.json','src/**/*.rs','Cargo.toml','Cargo.lock','*.程序文本','*.模块制品','*.技能制品','说明.md'):
        文件表.update(包目录.glob(通配形状))
    return {str(文件路径.relative_to(包目录)):hashlib.sha256(文件路径.read_bytes()).hexdigest()
            for 文件路径 in sorted(文件表) if 文件路径.is_file()}


def 处理扩展指纹(仓根, 是检查):
    失败表 = []
    for 声明路径 in sorted((仓根/'扩展根目录').glob('*/*/包声明.json')):
        包目录 = 声明路径.parent
        指纹路径 = 包目录/'指纹.json'
        旧指纹 = json.loads(指纹路径.read_text()) if 指纹路径.is_file() else None
        if 旧指纹 and 旧指纹.get('生成器') != 生成器相对路径:
            continue
        新指纹 = 收集扩展指纹(包目录)
        if 是检查:
            旧表 = (旧指纹 or {}).get('指纹',{})
            for 相对路径 in sorted(set(旧表)|set(新指纹)):
                if 旧表.get(相对路径)!=新指纹.get(相对路径):
                    失败表.append('%s：%s'%(包目录.relative_to(仓根),相对路径))
        else:
            指纹正文 = dict(算法='sha256',生成器=生成器相对路径,
                生成物声明='生成物，禁手改。生成器：'+生成器相对路径,
                生成命令='python3 '+生成器相对路径,
                范围='声明、Rust源码、Cargo清单与锁文件、程序文本、模块及技能制品；不含机器局部支持库制品、说明散文、缓存、指纹本身。',指纹=新指纹)
            指纹路径.write_text(json.dumps(指纹正文,ensure_ascii=False,indent=2)+'\n')
    if 失败表:
        print('扩展指纹不一致：\n'+'\n'.join(失败表))
        return 1
    return 0


def 入口函数(参数表):
    return 处理扩展指纹(Path(__file__).resolve().parents[3], '--检查' in 参数表)
