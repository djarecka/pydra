# local build environment

function travis_before_install {
    travis_retry python -m pip install --upgrade $INSTALL_DEPENDS
    sudo apt-get update;
    sudo apt-get install flawfinder squashfs-tools uuid-dev libuuid1 libffi-dev libssl-dev libssl1.0.0 \
    libarchive-dev libgpgme11-dev libseccomp-dev wget gcc make pkg-config -y;
    wget https://dl.google.com/go/go1.13.4.linux-amd64.tar.gz;
    sudo tar -C /usr/local -xzf go1.13.4.linux-amd64.tar.gz;
    export GOPATH=${HOME}/go;
    export PATH=/usr/local/go/bin:${PATH}:${GOPATH}/bin;
    export VERSION=3.5.0;
    wget https://github.com/sylabs/singularity/releases/download/v${VERSION}/singularity-${VERSION}.tar.gz;
    tar -xzf singularity-${VERSION}.tar.gz;
    cd singularity;
    ./mconfig;
    make -C ./builddir;
    sudo make -C ./builddir install;
    cd -
}

function travis_install {
    if [ "$CHECK_TYPE" = "test" ]; then
        if [ "$INSTALL_TYPE" = "pip" ]; then
            pip install $PIP_ARGS .
        elif [ "$INSTALL_TYPE" = "install" ]; then
            python setup.py install
        elif [ "$INSTALL_TYPE" = "develop" ]; then
            python setup.py develop
        elif [ "$INSTALL_TYPE" = "sdist" ]; then
            python setup.py sdist
            pip install dist/*.tar.gz
        elif [ "$INSTALL_TYPE" = "wheel" ]; then
            python setup.py bdist_wheel
            pip install dist/*.whl
        fi
        # Verify import with bare install
        python -c 'import pydra; print(pydra.__version__)'
    fi
}

function travis_before_script {
    if [ "$CHECK_TYPE" = "test" ]; then
        # Install test dependencies using similar methods...
        # Extras are interpreted by pip, not setup.py, so develop becomes editable
        # and install just becomes pip
        if [ "$INSTALL_TYPE" = "develop" ]; then
            pip install -e ".[test]"
        elif [ "$INSTALL_TYPE" = "sdist" ]; then
            pip install "$( ls dist/pydra*.tar.gz )[test]"
        elif [ "$INSTALL_TYPE" = "wheel" ]; then
            pip install "$( ls dist/pydra*.whl )[test]"
        else
            # extras don't seem possible with setup.py install, so switch to pip
            pip install ".[test]"
        fi
    elif [ "$CHECK_TYPE" = "style" ]; then
        pip install black==19.3b0
    fi
}

function travis_script {
    if [ "$CHECK_TYPE" = "test" ]; then
        pytest -vs -n auto pydra/engine/tests/test_sing*.py
    elif [ "$CHECK_TYPE" = "style" ]; then
        black --check pydra tools setup.py
    fi
}

function travis_after_script {
    codecov --file cov.xml --flags unittests -e TRAVIS_JOB_NUMBER
}
