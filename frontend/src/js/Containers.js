import React from 'react'
import { Collapse } from 'reactstrap';
import {LinearProgress} from 'rmwc/LinearProgress';
import {Icon} from 'rmwc/Icon';

import {FlexCol, FlexCont} from "./shared_components/Flex";
import ContainerIcon from "./shared_components/ContainerIcon";
import Container from "./Container";

export default class Containers extends React.Component {

    constructor(props) {
        super(props);
        this.state = {
            loaded: false,
            containers: []
        };
    }

    componentDidMount() {
        this.initNodeInfoChecker();
    }

    componentWillUnmount() {
        this.destroyInfoChecker();
    }

    destroyInfoChecker() {
        clearInterval(this.state.containersInfoTimer)
    }

    initNodeInfoChecker() {
        this.checkContainersInfo();
        this.setState({
            containersInfoTimer: setInterval(() => {
                this.checkContainersInfo()
            }, 6000),
        });
    }

    checkContainersInfo() {
        const url = this.props.fetchUrl;
        let self = this;
        fetch(url)
            .then((resp) => resp.json())
            .then(function (data) {
                self.setState({
                    containers: data.data,
                    loaded: true
                });
            })
            .catch(function (error) {
                console.log(error);
            });
    }

    render() {

        const containers = this.state.containers.map((container, i) =>
            <div key={i}>
                <Container container={container} darkMode={this.props.darkMode}/>
            </div>
        );

        let content = (
            <div style={{marginTop: '-10px', marginBottom: '-10px'}}>
              {(containers.length > 0) ? containers : <p className='padd-top-md text-center g-4'>No containers</p>}
            </div>
        );

        return (
            <div className="">
                {this.state.loaded ? content : <LinearProgress determinate={false}></LinearProgress>}
            </div>
        );
    }
}
