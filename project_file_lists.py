import os

def create_project_tree(start_path='.', output_file='project_tree.txt'):
    # Git, 가상환경, 컴파일된 파일 등 구조 파악에 불필요한 폴더 제외
    exclude_dirs = {'.git', '__pycache__', 'venv', 'env', '.vscode', '.idea', 'build', 'dist'}
    
    with open(output_file, 'w', encoding='utf-8') as f:
        for root, dirs, files in os.walk(start_path):
            dirs[:] = [d for d in dirs if d not in exclude_dirs]
            
            level = root.replace(start_path, '').count(os.sep)
            indent = '│   ' * level
            
            # 최상위 폴더 이름 처리
            folder_name = os.path.basename(root) 
            if root == start_path:
                folder_name = os.path.basename(os.path.abspath(start_path))
            
            f.write(f"{indent}├── {folder_name}/\n")
            
            sub_indent = '│   ' * (level + 1)
            for file in files:
                # pyc 파일이나 맥 OS 시스템 파일 등 불필요한 파일 제외
                if not file.endswith('.pyc') and file != '.DS_Store':
                    f.write(f"{sub_indent}├── {file}\n")
                    
    print(f"[{output_file}] 파일에 프로젝트 구조가 저장되었습니다.")

if __name__ == '__main__':
    create_project_tree()