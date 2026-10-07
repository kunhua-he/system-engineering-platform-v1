"""309声明经真实生成、契约编译与运行读取的正反样本。"""
import copy
import json
from pathlib import Path
import shutil
import struct
import subprocess
import tempfile
from .路径形状 import 仓根


def 验证参数生成():
    仓库 = Path(仓根)
    构建目录 = 仓库 / "构建环境"
    构建目录.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="参数生成验证-", dir=构建目录) as 临时目录:
        声明目录 = Path(临时目录)
        (声明目录 / "src").mkdir()
        原声明 = 仓库 / "扩展根目录/原子支持库/编译器支持库"
        shutil.copy(原声明 / "包声明.json", 声明目录)
        for 目录名 in ("类型声明", "错误码表"):
            shutil.copytree(原声明 / 目录名, 声明目录 / 目录名)
        (声明目录 / "能力声明").mkdir()
        shutil.copy(原声明 / "能力声明/1101.json", 声明目录 / "能力声明/1101.json")
        源文件 = 声明目录 / "能力声明/1101.json"
        声明内容 = json.loads(源文件.read_text())
        参数种类 = [(4, None), (4, {"类型标签": 0, "值": 0}),
                    (4, {"类型标签": 4, "文本": "中文\x00默认\n"}),
                    (2, {"类型标签": 2, "值": struct.unpack("<Q", struct.pack("<d", -1.25))[0]}),
                    (1, {"类型标签": 1, "值": 18446744073709551615}),
                    (3, {"类型标签": 3, "值": 1}), (4, {"类型标签": 4, "文本": ""})]
        声明内容["参数表"] = []
        for 标签, 默认值 in 参数种类:
            参数行 = {"名称": "样本参数", "说明": "真实生成样本", "类型标签": 标签, "状态位": 0}
            if 默认值 is not None:
                参数行["默认值"] = 默认值
            声明内容["参数表"].append(参数行)
        源文件.write_text(json.dumps(声明内容, ensure_ascii=False))
        生成命令 = ["python3", str(仓库 / "构建装配/形态装配/生成声明.py"), "--声明根", str(声明目录.relative_to(仓库))]
        subprocess.run(生成命令, cwd=仓库, check=True, capture_output=True)
        subprocess.run(生成命令 + ["--检查"], cwd=仓库, check=True, capture_output=True)
        契约产物 = 声明目录 / "libv1_contract.rlib"
        subprocess.run(["rustc", "--edition=2024", "--crate-name", "v1_contract", "--crate-type", "rlib", str(仓库 / "契约声明/src/lib.rs"), "-o", str(契约产物)], cwd=仓库, check=True, capture_output=True)
        测试源码 = 声明目录 / "验证.rs"
        测试源码.write_text('''#![allow(non_snake_case, dead_code, unused_imports)]
#[path = "src/声明数据.rs"] mod 声明数据;
fn main() {
    use 声明数据::{取生成默认值, 取生成参数};
    use v1_contract::{数据槽, 类型标签, 槽标志};
    assert_eq!(取生成默认值(1101, 0), None);
    assert_eq!(取生成默认值(1101, 1), Some(数据槽::空槽()));
    let 文本槽 = 取生成默认值(1101, 2).unwrap();
    assert!(文本槽.是否引用());
    assert!(!文本槽.交出了所有权());
    assert_ne!(文本槽.槽标志位 & 槽标志::只读, 0);
    let 文本字节 = unsafe { core::slice::from_raw_parts(文本槽.槽值 as *const u8, 文本槽.槽字节长度 as usize) };
    assert_eq!(文本字节, "中文\\0默认\\n".as_bytes());
    assert_eq!(文本槽.槽值, 取生成默认值(1101, 2).unwrap().槽值);
    let 浮点槽 = 取生成默认值(1101, 3).unwrap();
    assert_eq!(f64::from_bits(浮点槽.槽值), -1.25);
    assert_eq!(浮点槽, 数据槽::内联槽(类型标签::构造(2), (-1.25f64).to_bits(), 8));
    assert_eq!(取生成默认值(1101, 4).unwrap().槽值 as i64, -1);
    assert_eq!(取生成默认值(1101, 5), Some(数据槽::内联槽(类型标签::构造(3), 1, 1)));
    assert_eq!(取生成默认值(1101, 6).unwrap().槽字节长度, 0);
    assert_eq!(取生成参数(1101, 2).unwrap().默认值, 文本槽);
    assert!(取生成参数(1101, 7).is_none());
    println!("真实读取：三态/UTF-8及空字节/静态所有权/浮点/整数/逻辑/空文本 通过");
}
''')
        执行文件 = 声明目录 / "验证"
        subprocess.run(["rustc", "--edition=2024", "--crate-name", "parameter_probe", str(测试源码), "--extern", "v1_contract=" + str(契约产物), "-o", str(执行文件)], cwd=仓库, check=True, capture_output=True)
        subprocess.run([str(执行文件)], check=True)
        for 默认值 in (None, {"类型标签": 1, "值": 0}, {"类型标签": 4, "值": 0}, {"类型标签": 0, "文本": "丢失"}, {"类型标签": 4, "文本": 42}, {"类型标签": 4, "文本": "冲突", "值": 0}, {"类型标签": 4, "文本": "\ud800"}, {"类型标签": 0, "值": False}):
            坏声明 = copy.deepcopy(声明内容)
            坏声明["参数表"][0]["默认值"] = 默认值
            源文件.write_text(json.dumps(坏声明, ensure_ascii=True))
            读数 = subprocess.run(生成命令, cwd=仓库, capture_output=True)
            assert 读数.returncode == 2, 读数.stderr
        源文件.write_text(json.dumps(声明内容, ensure_ascii=False))
        类型文件 = 声明目录 / "类型声明/0100.json"
        类型内容 = json.loads(类型文件.read_text())
        # 正向：合法非空 元素表（`契约声明/格式说明.md` §四 形状 {名称,类型标签,说明}）⇒ 过，
        # 且生成物照常可编译消费（下一条 --检查 即“生成物可被消费”）；4 是底座标签、100 是本声明标签。
        类型内容["元素表"] = [{"名称": "元素", "类型标签": 4, "说明": "正式结构字段"},
                            {"名称": "另一元素", "类型标签": 100, "说明": "复用本声明类型"}]
        类型文件.write_text(json.dumps(类型内容, ensure_ascii=False))
        读数 = subprocess.run(生成命令, cwd=仓库, capture_output=True)
        assert 读数.returncode == 0, 读数.stderr
        subprocess.run(生成命令 + ["--检查"], cwd=仓库, check=True, capture_output=True)
        # 反向：形状错四类（缺字段 / 类型标签非整 / 类型标签不在表 / 重名）⇒ 红且定位到位
        for 元素表样本 in (
            [{"名称": "缺类型标签", "说明": "x"}],
            [{"名称": "非整型标签", "类型标签": "4", "说明": "x"}],
            [{"名称": "表里没有的标签", "类型标签": 9999, "说明": "x"}],
            [{"名称": "重名", "类型标签": 4, "说明": "a"},
             {"名称": "重名", "类型标签": 1, "说明": "b"}],
        ):
            类型内容["元素表"] = 元素表样本
            类型文件.write_text(json.dumps(类型内容, ensure_ascii=True))
            读数 = subprocess.run(生成命令, cwd=仓库, capture_output=True)
            assert 读数.returncode == 2 and "元素表" in 读数.stderr.decode(), 读数.stderr
        # 空表仍过（原行为不变）
        类型内容["元素表"] = []
        类型文件.write_text(json.dumps(类型内容, ensure_ascii=False))
        读数 = subprocess.run(生成命令, cwd=仓库, capture_output=True)
        assert 读数.returncode == 0, 读数.stderr
        print("真实生成：合法非空元素表过且生成物可编译消费 · 错形状4类红且定位到位 · 空表仍过")
