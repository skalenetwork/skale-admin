import React from 'react'
import {LinearProgress} from 'rmwc/LinearProgress';

export default class Web3Connection extends React.Component {
    render() {
        return (
            <div className={(this.props.darkMode ? 'dark-mode' : '')}>
                <div className={"cont fl-cont fl-center web3connection"} style={{textAlign: "center", height: "100vh"}}>
                    <div className="fl-wrap fl-grow">
                        <h2>Connecting to the Web3</h2>
                        <h6 className="padd-bott-md lite-gr-col" style={{lineHeight: "1.6"}}>
                            Please note that Metamask plugin should be installed in order to use this application. <br/>
                            If you're seeing this more than a few seconds, probably you don't.
                        </h6>
                        <div style={{width: "340px", margin: "auto"}}>
                            <LinearProgress determinate={false}></LinearProgress>
                        </div>
                    </div>
                </div>
            </div>
        );
    }
}
