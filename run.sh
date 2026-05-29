#!/bin/bash

# 检查是否在虚拟环境中
if [[ -z "$VIRTUAL_ENV" ]]; then
    # 检查虚拟环境是否存在
    if [[ ! -d "venv" ]]; then
        echo "创建虚拟环境..."
        python3 -m venv venv
    fi
    
    echo "激活虚拟环境..."
    source venv/bin/activate
fi
pip install flask pillow requests numpy
python ai.py
