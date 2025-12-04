# 既にビルド済みのHEASoftイメージをベースにする
FROM heasoft:v6.36

# 一時的にrootになって権限周りを設定
USER root

# 1. Git, Sudo, 便利なツールをインストール
# 2. heasoftユーザーにsudo権限を付与
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y \
    git \
    sudo \
    curl \
    vim \
    nano \
    tree \
    locales \
    && echo "en_US.UTF-8 UTF-8" > /etc/locale.gen \
    && locale-gen en_US.UTF-8 \
    && update-locale LANG=en_US.UTF-8 \
    && echo "heasoft ALL=(ALL) NOPASSWD:ALL" > /etc/sudoers.d/heasoft \
    && chmod 0440 /etc/sudoers.d/heasoft \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# 環境変数を固定する
ENV LANG=en_US.UTF-8
ENV LC_ALL=en_US.UTF-8

# 作業ユーザーを heasoft に戻す
USER heasoft

# 作業ディレクトリの設定
WORKDIR /workspaces/HEASoft

# --- 便利ツールのセットアップ ---

# 1. Starship (プロンプト) のインストール
RUN curl -sS https://starship.rs/install.sh | sudo sh -s -- -y \
    && echo 'eval "$(starship init bash)"' >> ~/.bashrc

# (オプション) 初回起動時のコマンド
CMD ["/bin/bash"]