use crate::contract_impl::代际令牌;
use std::fs::{self, OpenOptions};
use std::io::{self, Read, Write};
use std::path::{Path, PathBuf};
use std::time::{SystemTime, UNIX_EPOCH};

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum 跨进程租约错误 {
    已占用,
    令牌不符,
    记录损坏,
    文件(io::ErrorKind),
}

impl From<io::Error> for 跨进程租约错误 {
    fn from(错误: io::Error) -> Self {
        Self::文件(错误.kind())
    }
}

pub struct 跨进程租约 {
    路径: PathBuf,
    令牌: 代际令牌,
    已释放: bool,
}

impl 跨进程租约 {
    pub fn 申请(
        路径: impl AsRef<Path>, 令牌: 代际令牌
    ) -> Result<Self, 跨进程租约错误> {
        let 路径 = 路径.as_ref().to_owned();
        let 内容 = format!(
            "版本=1\n进程号={}\n令牌={}\n时间={}\n",
            std::process::id(),
            令牌.十六进制(),
            SystemTime::now()
                .duration_since(UNIX_EPOCH)
                .unwrap_or_default()
                .as_secs()
        );
        let mut 文件 = match OpenOptions::new().write(true).create_new(true).open(&路径) {
            Ok(句柄) => 句柄,
            Err(错误) if 错误.kind() == io::ErrorKind::AlreadyExists => {
                return Err(跨进程租约错误::已占用);
            }
            Err(错误) => return Err(错误.into()),
        };
        文件.write_all(内容.as_bytes())?;
        文件.sync_all()?;
        Ok(Self {
            路径,
            令牌,
            已释放: false,
        })
    }

    fn 读取令牌(路径: &Path) -> Result<代际令牌, 跨进程租约错误> {
        let mut 内容 = String::new();
        fs::File::open(路径)?.read_to_string(&mut 内容)?;
        let 记录令牌文本 = 内容
            .lines()
            .find_map(|行| 行.strip_prefix("令牌="))
            .ok_or(跨进程租约错误::记录损坏)?;
        代际令牌::从十六进制(记录令牌文本).map_err(|_| 跨进程租约错误::记录损坏)
    }

    pub fn 接管(
        路径: impl AsRef<Path>, 令牌: 代际令牌
    ) -> Result<Self, 跨进程租约错误> {
        let 路径 = 路径.as_ref().to_owned();
        let 记录令牌 = Self::读取令牌(&路径)?;
        if 记录令牌 != 令牌 {
            return Err(跨进程租约错误::令牌不符);
        }
        Ok(Self {
            路径,
            令牌,
            已释放: false,
        })
    }

    pub fn 路径(&self) -> &Path {
        &self.路径
    }

    pub fn 令牌(&self) -> 代际令牌 {
        self.令牌
    }

    pub fn 释放(&mut self) -> Result<(), 跨进程租约错误> {
        if !self.已释放 {
            let 当前令牌 = Self::读取令牌(&self.路径)?;
            if 当前令牌 != self.令牌 {
                return Err(跨进程租约错误::令牌不符);
            }
            fs::remove_file(&self.路径)?;
            self.已释放 = true;
        }
        Ok(())
    }
}

impl Drop for 跨进程租约 {
    fn drop(&mut self) {
        let _ = self.释放();
    }
}
