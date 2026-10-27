# -*- coding: utf-8 -*-
"""常量 —— 库格式号 / 结构字段表 / 状态位 / 数值格式（原 `接缝反解.py` 模块级常量，纯搬家）。"""

库格式号 = 0x01312D65          # =20000101，LIB_INFO 第一个 DWORD
导出名 = b"GetNewInf"          # 实测全部 .fne 都导出此名
库信息大小 = 0x90
命令项大小, 参数项大小, 常量项大小, 类型项大小 = 0x24, 0x18, 0x20, 0x38

# 结构定义：偏移 · 宽度 · 名称 · 类别(u32/i32/u16/i16/f64/ptr/str)
库信息字段 = [
    (0x00, 4, "m_dwLibFormatVer", "u32"), (0x04, 4, "m_szGuid", "str"), (0x08, 4, "m_nMajorVersion", "i32"),
    (0x0C, 4, "m_nMinorVersion", "i32"), (0x10, 4, "m_nBuildNumber", "i32"), (0x14, 4, "m_nRqSysMajorVer", "i32"),
    (0x18, 4, "m_nRqSysMinorVer", "i32"), (0x1C, 4, "m_nRqSysKrnlLibMajorVer", "i32"), (0x20, 4, "m_nRqSysKrnlLibMinorVer", "i32"),
    (0x24, 4, "m_szName", "str"), (0x28, 4, "m_nLanguage", "i32"), (0x2C, 4, "m_szExplain", "str"),
    (0x30, 4, "m_dwState", "u32"), (0x34, 4, "m_szAuthor", "str"), (0x38, 4, "m_szZipCode", "str"),
    (0x3C, 4, "m_szAddress", "str"), (0x40, 4, "m_szPhoto", "str"), (0x44, 4, "m_szFax", "str"),
    (0x48, 4, "m_szEmail", "str"), (0x4C, 4, "m_szHomePage", "str"), (0x50, 4, "m_szOther", "str"),
    (0x54, 4, "m_nDataTypeCount", "u32"), (0x58, 4, "m_pDataType", "ptr"), (0x5C, 4, "m_nCategoryCount", "u32"),
    (0x60, 4, "m_szzCategory", "ptr"), (0x64, 4, "m_nCmdCount", "u32"), (0x68, 4, "m_pBeginCmdInfo", "ptr"),
    (0x6C, 4, "m_pCmdsFunc", "ptr"), (0x70, 4, "m_pfnRunAddInFn", "ptr"), (0x74, 4, "m_szzAddInFnInfo", "ptr"),
    (0x78, 4, "m_pfnNotify", "ptr"), (0x7C, 4, "m_pfnSuperTemplate", "ptr"), (0x80, 4, "m_szzSuperTemplateInfo", "ptr"),
    (0x84, 4, "m_nLibConstCount", "u32"), (0x88, 4, "m_pLibConst", "ptr"), (0x8C, 4, "m_szzDependFiles", "ptr"),
]
命令字段 = [
    (0x00, 4, "m_szName", "str"), (0x04, 4, "m_szEgName", "str"), (0x08, 4, "m_szExplain", "str"),
    (0x0C, 2, "m_shtCategory", "i16"), (0x0E, 2, "m_wState", "u16"), (0x10, 4, "m_dtRetValType", "u32"),
    (0x14, 2, "m_wReserved", "u16"), (0x16, 2, "m_shtUserLevel", "i16"), (0x18, 2, "m_shtBitmapIndex", "i16"),
    (0x1A, 2, "m_shtBitmapCount", "i16"), (0x1C, 4, "m_nArgCount", "u32"), (0x20, 4, "m_pBeginArgInfo", "ptr"),
]
参数字段 = [
    (0x00, 4, "m_szName", "str"), (0x04, 4, "m_szExplain", "str"), (0x08, 2, "m_shtBitmapIndex", "i16"),
    (0x0A, 2, "m_shtBitmapCount", "i16"), (0x0C, 4, "m_dtType", "u32"), (0x10, 4, "m_nDefault", "i32"),
    (0x14, 4, "m_dwState", "u32"),
]
常量字段 = [
    (0x00, 4, "m_szName", "str"), (0x04, 4, "m_szEGName", "str"), (0x08, 4, "m_szExplain", "str"),
    (0x0C, 2, "m_shtReserved", "i16"), (0x0E, 2, "m_shtType", "i16"), (0x10, 4, "m_szText", "str"),
    (0x18, 8, "m_dbValue", "f64")]        # 自然对齐：DOUBLE 落在 8 的倍数上
类型字段 = [
    (0x00, 4, "m_szName", "str"), (0x04, 4, "m_szEgName", "str"), (0x08, 4, "m_szExplain", "str"),
    (0x0C, 4, "m_nCmdCount", "u32"), (0x10, 4, "m_pnCmdsIndex", "ptr"), (0x14, 4, "m_dwState", "u32"),
    (0x18, 4, "m_dwUnitBmpID", "u32"), (0x1C, 4, "m_nEventCount", "u32"), (0x20, 4, "m_pEventBegin", "ptr"),
    (0x24, 4, "m_nPropertyCount", "u32"), (0x28, 4, "m_pPropertyBegin", "ptr"), (0x2C, 4, "m_pfnGetInterface", "ptr"),
    (0x30, 4, "m_nElementCount", "u32"), (0x34, 4, "m_pElementBegin", "ptr")]
命令状态位 = {2: "隐含", 3: "错误", 4: "发布禁用", 5: "可追加参数", 6: "返回数组", 7: "对象拷贝", 8: "对象释放", 9: "对象构造"}
库状态位 = {2: "无运行代码", 3: "无编辑信息", 5: "数据库库", 7: "实为LIB_INFO2", 8: "IDE插件"}
数值格式 = {"u32": "<I", "i32": "<i", "u16": "<H", "i16": "<h", "f64": "<d"}
