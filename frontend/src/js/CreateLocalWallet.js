import React from 'react'
import {Link} from 'react-router-dom'
import {withRouter} from 'react-router-dom';

import {Icon} from 'rmwc/Icon';
import {LinearProgress} from 'rmwc/LinearProgress';
import Button from './SkaleButton/SkaleButton';

class CreateLocalWallet extends React.Component {


    constructor(props) {
        super(props);
        this.state = {
            loading: false
        };
        this.createWallet = this.createWallet.bind(this);
    }

    componentDidMount() {
        this.props.setMenuVisibility(true);
    }

    createWallet() { // todo: unused
        this.setState({loading: true});
        let self = this;
        fetch('/create-wallet', {
            method: 'POST',
            headers: {
                'Accept': 'application/json',
                'Content-Type': 'application/json',
            },
            //body: JSON.stringify(nodeConfig)
        }).then(function (response) {
            return response.json()
        }, function (error) {
            console.error(error.message);
        }).then(function (data) {
            self.props.history.push('/local-wallet/' + data.address);
        })
    }

    render() {
        return (
            <div className="marg-30">
                <div className="fl-cont fl-center-vert content-center">
                    <div className="fl-col fl-grow"></div>
                    <div className="fl-col fl-grow text-center">

                        <div className={this.state.loading ? '' : 'hidden'}>
                            <h4 className="padd-bott-10">Generating wallet</h4>
                            <div style={{width: "340px", margin: "auto"}}>
                                <LinearProgress determinate={false}></LinearProgress>
                            </div>
                        </div>


                        <div className={this.state.loading ? 'hidden' : ''}>
                            <h2 className=''>
                                Welcome to SKALE Node UI
                            </h2>
                            <h6 className="marg-bott-big fw-4 g-4">
                                Go to local wallet to stake SKL tokens and create a node
                            </h6>
                            <Link to='/local-wallet' className='undec'>
                                <Button size="lg">
                                    Go to local wallet
                                    <Icon strategy="ligature"
                                          className="white-icon sm-icon marg-left-10">arrow_forward</Icon>
                                </Button>
                            </Link>
                        </div>
                    </div>
                    <div className="fl-col fl-grow"></div>
                </div>
            </div>
        )
    }
}

export default withRouter(CreateLocalWallet);