# local build environment

function travis_before_install {
      choco install python3;
      export PATH="/c/Python37:/c/Python37/Scripts:$PATH";
      travis_retry python -m pip install --upgrade $INSTALL_DEPENDS
      echo "my python pip"
      echo $(python --version)
      echo $(pip --version)
}

function travis_install {
    if [ "$CHECK_TYPE" = "test" ]; then
        echo "Hello from pip"
        pip install $PIP_ARGS .
        # Verify import with bare install
        python -c 'import pydra; print(pydra.__version__)'
    fi
}

function travis_before_script {
    if [ "$CHECK_TYPE" = "test" ]; then
        # Install test dependencies using similar methods...
        pip install ".[test]"
    fi
}

function travis_script {
    if [ "$CHECK_TYPE" = "test" ]; then
        pytest -vs -n auto --cov pydra --cov-config .coveragerc --cov-report xml:cov.xml --doctest-modules pydra
    fi
}

function travis_after_script {
    codecov --file cov.xml --flags unittests -e TRAVIS_JOB_NUMBER
}
